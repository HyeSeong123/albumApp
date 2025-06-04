from PIL import Image, ExifTags
import os
import re
import logging
from datetime import datetime
from typing import Dict, Optional, Union, BinaryIO
from PIL import Image, ExifTags, ImageFile
from PIL.ExifTags import TAGS, GPSTAGS
import os
import sqlite3
from datetime import datetime

# 부분적으로 로드된 이미지도 처리할 수 있도록 설정
ImageFile.LOAD_TRUNCATED_IMAGES = True

logger = logging.getLogger(__name__)

class PhotoDateExtractor:
    @staticmethod
    def extract_date_from_filename(filename: str) -> Optional[str]:
        """
        파일명에서 날짜를 추출합니다.
        
        지원하는 형식:
        - KakaoTalk_20241223_112651710_14.jpg
        - 20150213_120514.jpg
        - 2011-08-04 15.36.21.jpg
        - 20250531-IMG_8503
        - 1358858786526.jpg (유닉스 타임스탬프)
        - IMG_20230515_123456.jpg
        - 2023-05-15_12-34-56.jpg
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # 파일 확장자 제거
        filename_without_ext = os.path.splitext(filename)[0]
        logger.debug(f"파일명에서 확장자 제거: {filename} -> {filename_without_ext}")
        
        patterns = [
            # 1. 카카오톡 형식: KakaoTalk_20241223_112651710_14
            (r'KakaoTalk[_-](\d{4})(\d{2})(\d{2})', '%Y%m%d'),
            
            # 2. YYYYMMDD_HHMMSS 형식: 20150213_120514
            (r'(\d{4})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})', '%Y%m%d%H%M%S'),
            
            # 3. YYYY-MM-DD HH.MM.SS 형식: 2011-08-04 15.36.21
            (r'(\d{4})[\-/\.](\d{2})[\-/\.](\d{2})[ _](\d{2})[:\-](\d{2})[:\-](\d{2})', '%Y%m%d%H%M%S'),
            
            # 4. YYYYMMDD-IMG_XXXX 형식: 20250531-IMG_8503
            (r'^(\d{4})(\d{2})(\d{2})[-_].*', '%Y%m%d'),
            
            # 5. IMG_YYYYMMDD_HHMMSS 형식: IMG_20230515_123456
            (r'[iI][mM][gG][_-](\d{4})(\d{2})(\d{2})[_-]?(\d{2})(\d{2})(\d{2})', '%Y%m%d%H%M%S'),
            
            # 6. YYYY-MM-DD_HH-MM-SS 형식: 2023-05-15_12-34-56
            (r'(\d{4})-(\d{2})-(\d{2})[_ ](\d{2})-(\d{2})-(\d{2})', '%Y%m%d%H%M%S'),
            
            # 7. YYYYMMDD 형식: 20230515
            (r'^(\d{4})(\d{2})(\d{2})$', '%Y%m%d'),
            
            # 8. YYYY-MM-DD 형식: 2023-05-15
            (r'^(\d{4})-(\d{2})-(\d{2})$', '%Y%m%d'),
            
            # 9. 유닉스 타임스탬프 (10자리 또는 13자리)
            (r'^(\d{10,13})$', 'unix')
        ]
        
        logger.debug(f"파일명에서 날짜 추출 시도: {filename_without_ext}")
        
        for pattern, fmt in patterns:
            try:
                match = re.search(pattern, filename_without_ext, re.IGNORECASE)
                if match:
                    logger.debug(f"패턴 매칭 성공 - 패턴: {pattern}, 그룹: {match.groups()}")
                    
                    if fmt == 'unix':
                        ts = int(match.group(1))
                        if ts > 1e12:  # 밀리초 단위
                            ts = ts // 1000
                        result = datetime.fromtimestamp(ts).isoformat()
                        logger.debug(f"유닉스 타임스탬프 변환: {ts} -> {result}")
                        return result
                    else:
                        # 그룹을 하나의 문자열로 합치기
                        cleaned = ''.join(match.groups())
                        # 형식에 따라 ISO 형식 또는 날짜만 반환
                        if 'H' in fmt:  # 시간 정보가 있는 경우
                            result = datetime.strptime(cleaned, fmt).isoformat()
                        else:  # 날짜만 있는 경우
                            result = datetime.strptime(cleaned, fmt).strftime('%Y-%m-%dT00:00:00')
                        logger.debug(f"날짜 변환: {cleaned} ({fmt}) -> {result}")
                        return result
            except Exception as e:
                logger.warning(f"날짜 파싱 오류 - 패턴: {pattern}, 파일명: {filename}, 오류: {str(e)}")
                continue
        
        logger.warning(f"일치하는 날짜 패턴을 찾을 수 없음: {filename}")
        return None

    @staticmethod
    def extract_date_from_exif(img: Image.Image) -> Optional[str]:
        try:
            exif = img._getexif()
            if not exif:
                return None
            for tag_id, value in exif.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                if tag in ['DateTimeOriginal', 'DateTimeDigitized', 'DateTime']:
                    try:
                        return datetime.strptime(value, "%Y:%m:%d %H:%M:%S").isoformat()
                    except:
                        continue
        except:
            pass
        return None

    @classmethod
    def extract_metadata_from_image(cls, img: Union[Image.Image, BinaryIO, str]) -> Dict[str, Optional[str]]:
        """
        이미지 객체 또는 파일 경로에서 메타데이터를 추출합니다.
        
        Args:
            img: PIL.Image.Image 객체, 파일 경로, 또는 파일과 같은 객체
            
        Returns:
            메타데이터를 포함한 딕셔너리 (width, height, taken_at)
        """
        logger = logging.getLogger(__name__)
        metadata = {
            'width': None,
            'height': None,
            'taken_at': None
        }
        
        try:
            # 이미지가 파일 경로나 파일과 같은 객체인 경우 열기
            if not isinstance(img, Image.Image):
                if hasattr(img, 'seek'):
                    img.seek(0)  # 파일 포인터를 처음으로 되돌림
                img = Image.open(img)
            
            # 이미지 크기 설정
            metadata['width'], metadata['height'] = img.size
            
            # EXIF에서 날짜 추출 시도
            try:
                metadata['taken_at'] = cls.extract_date_from_exif(img)
                if metadata['taken_at']:
                    logger.debug(f"EXIF에서 날짜 추출 성공: {metadata['taken_at']}")
            except Exception as ex:
                logger.warning(f"EXIF에서 날짜 추출 실패: {str(ex)}", exc_info=True)
            
            # 이미지가 열려있다면 닫기
            if hasattr(img, 'close') and img is not None:
                img.close()
                
        except Exception as e:
            logger.error(f"이미지 메타데이터 추출 중 오류: {str(e)}", exc_info=True)
        
        return metadata
    
    @staticmethod
    def extract_metadata(image_path: str) -> Dict[str, Optional[str]]:
        """
        이미지 파일에서 메타데이터를 추출합니다.
        
        Args:
            image_path: 이미지 파일 경로
            
        Returns:
            메타데이터를 포함한 딕셔너리 (width, height, taken_at)
        """
        metadata = {
            'width': None, 
            'height': None, 
            'taken_at': None
        }
        
        filename = os.path.basename(image_path)
        logger = logging.getLogger(__name__)
        
        try:
            # 1. 파일명에서 날짜 추출 시도
            date_from_filename = PhotoDateExtractor.extract_date_from_filename(filename)
            if date_from_filename:
                metadata['taken_at'] = date_from_filename
                logger.debug(f"파일명에서 날짜 추출: {date_from_filename}")
            
            # 2. 이미지 파일 열기
            with Image.open(image_path) as img:
                metadata['width'], metadata['height'] = img.size
                
                # 3. EXIF에서 날짜 추출 시도 (아직 날짜를 찾지 못한 경우)
                if not metadata['taken_at']:
                    exif_date = PhotoDateExtractor.extract_date_from_exif(img)
                    if exif_date:
                        metadata['taken_at'] = exif_date
                        logger.debug(f"EXIF에서 날짜 추출: {exif_date}")
            
            # 4. 여전히 날짜를 찾지 못한 경우 현재 시간 사용
            if not metadata['taken_at']:
                metadata['taken_at'] = datetime.now().isoformat()
                logger.warning(f"날짜를 찾을 수 없어 현재 시간 사용: {filename}")
                
        except Exception as e:
            logger.error(f"이미지 메타데이터 추출 실패 - {filename}: {str(e)}", exc_info=True)
            # 오류 발생 시 기본값 설정
            if not metadata['taken_at']:
                metadata['taken_at'] = datetime.now().isoformat()
        
        return metadata


def insert_photo_to_db(photo_info: dict) -> bool:
    """
    Inserts a photo's metadata into the database.

    Args:
        photo_info: A dictionary containing photo metadata.
                    Expected keys: 'id', 'album_id', 'filename', 'filepath', 
                                   'width', 'height', 'taken_at', 'memo'.
                    'album_id'는 선택적(optional)이며, None이거나 없으면 컬럼에서 제외됩니다.

    Returns:
        True if insertion was successful, False otherwise.
    """
    conn = None
    try:
        db_file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
            'album.db'
        )
        conn = sqlite3.connect(db_file_path)
        cursor = conn.cursor()
        now_iso = datetime.now().isoformat()

        columns = ["id", "filename", "filepath", "width", "height", "taken_at", "created_date", "modified_date", "memo"]
        values = [
            photo_info.get('id'),
            photo_info.get('filename'),
            photo_info.get('filepath'),
            photo_info.get('width'),
            photo_info.get('height'),
            photo_info.get('taken_at'),
            now_iso,  # created_date
            now_iso,  # modified_date
            photo_info.get('memo', '')
        ]
        if photo_info.get('album_id') is not None:
            columns.insert(1, "album_id")
            values.insert(1, photo_info.get('album_id'))

        query = f"INSERT INTO photo ({', '.join(columns)}) VALUES ({', '.join(['?']*len(columns))})"
        cursor.execute(query, values)
        conn.commit()
        logger.info(f"Photo {photo_info.get('id')} inserted into DB for album_id={photo_info.get('album_id')}")
        return True
    except sqlite3.IntegrityError as ie:
        logger.error(f"Database integrity error inserting photo {photo_info.get('id')}: {ie}.")
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error inserting photo {photo_info.get('id')}: {e}.")
        return False
    except Exception as ex:
        logger.error(f"Unexpected error inserting photo {photo_info.get('id')}: {ex}.", exc_info=True)
        return False
    finally:
        if conn:
            conn.close()
