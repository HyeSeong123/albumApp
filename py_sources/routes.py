from flask import Blueprint, render_template, request, jsonify, current_app
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from PIL import Image, ExifTags
import hashlib
import uuid

# DB insert 함수 임포트
from py_sources.models.photo_repository import PhotoDateExtractor, insert_photo_to_db, get_photo_filepaths_by_album_id
import json # JSON 처리를 위해 추가

main = Blueprint("main", __name__)

from flask import send_from_directory

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'resources', 'uploads')

@main.route('/uploads/<path:filename>')
def uploaded_file(filename):
    # 업로드 파일은 resources/uploads에서 서비스
    return send_from_directory(UPLOAD_FOLDER, filename)

# 업로드 폴더를 static/uploads로 설정
RESOURCES_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'resources')
UPLOAD_FOLDER = os.path.join(RESOURCES_FOLDER, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 썸네일 폴더도 resources/uploads/thumbnails로 설정
THUMBNAIL_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbnails')
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)

# 허용되는 이미지 확장자
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def fix_image_orientation(image_path):
    """이미지의 방향 정보(EXIF)를 확인하고 회전"""
    try:
        image = Image.open(image_path)
        if hasattr(image, '_getexif') and image._getexif() is not None:
            exif = {ExifTags.TAGS[k]: v for k, v in image._getexif().items() if k in ExifTags.TAGS}
            orientation = exif.get('Orientation', 1)
            
            # 방향에 따라 이미지 회전
            if orientation == 3:
                image = image.rotate(180, expand=True)
            elif orientation == 6:
                image = image.rotate(270, expand=True)
            elif orientation == 8:
                image = image.rotate(90, expand=True)
                
            # 회전된 이미지 저장 (원본 덮어쓰기)
            image.save(image_path)
            image.close()
    except Exception as e:
        current_app.logger.error(f'Error fixing image orientation: {str(e)}')

def create_thumbnail(image_path, output_path, size=(200, 200)):
    """썸네일 이미지 생성"""
    try:
        with Image.open(image_path) as img:
            # 이미지 비율 유지하며 리사이즈
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # 투명 배경을 하얀색으로 변환 (PNG 대비)
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])  # 알파 채널 마스크 사용
                img = background
            
            img.save(output_path, 'JPEG', quality=85)
    except Exception as e:
        current_app.logger.error(f'Error creating thumbnail: {str(e)}')

def save_uploaded_file(file, base_folder, album_id=None, keep_original_name=True):
    """
    업로드된 파일을 임시 경로에 저장 후 메타데이터 추출, 촬영일 기준 폴더/파일명으로 이동, DB 저장용 정보 반환
    DB에는 static/uploads 기준의 상대경로(uploads/...)로 저장
    """
    if not file or not allowed_file(file.filename):
        current_app.logger.error(f'유효하지 않은 파일 객체: {str(file)}')
        return None
    try:
        safe_filename = secure_filename(file.filename)
        name, ext = os.path.splitext(safe_filename)
        temp_folder = os.path.join(base_folder, "temp")
        os.makedirs(temp_folder, exist_ok=True)
        temp_path = os.path.join(temp_folder, safe_filename)
        file.save(temp_path)
        # 메타데이터 추출
        metadata = PhotoDateExtractor.extract_metadata(temp_path)
        taken_at = metadata.get('taken_at')
        if taken_at:
            try:
                dt = datetime.fromisoformat(taken_at)
            except Exception:
                dt = datetime.now()
        else:
            dt = datetime.now()
        date_path_segment = os.path.join(str(dt.year), f"{dt.month:02d}", f"{dt.day:02d}")
        # 저장 경로를 static/uploads 하위로 통일
        if album_id:
            save_folder = os.path.join(base_folder, album_id, date_path_segment)
            db_rel_path = os.path.join('uploads', album_id, date_path_segment, safe_filename).replace('\\', '/').replace('\\', '/')
        else:
            save_folder = os.path.join(base_folder, date_path_segment)
            db_rel_path = os.path.join('uploads', date_path_segment, safe_filename).replace('\\', '/').replace('\\', '/')
        os.makedirs(save_folder, exist_ok=True)
        final_path = os.path.join(save_folder, safe_filename)
        os.replace(temp_path, final_path)
        # 썸네일 생성
        thumbnail_folder = os.path.join(base_folder, 'thumbnails', album_id if album_id else '', date_path_segment)
        os.makedirs(thumbnail_folder, exist_ok=True)
        thumbnail_path = os.path.join(thumbnail_folder, safe_filename)
        create_thumbnail(final_path, thumbnail_path)
        fix_image_orientation(final_path)
        # DB에 저장할 정보 반환
        return {
            'filename': safe_filename,
            'filepath': db_rel_path, # uploads/... 형태로 저장
            'width': metadata.get('width'),
            'height': metadata.get('height'),
            'taken_at': metadata.get('taken_at'),
            'modified_date': datetime.now().isoformat(),
            'memo': '' # 초기 메모는 비워둠
        }
    except Exception as e:
        current_app.logger.error(f'save_uploaded_file 오류: {str(e)} - 파일: {file.filename if file else "N/A"}', exc_info=True)
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as ex_remove:
                current_app.logger.error(f'임시 파일 삭제 오류: {str(ex_remove)}')
        return None

        save_folder = os.path.join(base_folder, date_path_segment)
        # 최종 파일명 결정 (중복 방지 또는 원본명 유지)
        if keep_original_name:
            final_filename = safe_filename
            counter = 1
            # 파일명 중복 시 _숫자 추가
            while os.path.exists(os.path.join(save_folder, final_filename)):
                final_filename = f"{name}_{counter}{ext}"
                counter += 1
        else:
            # 고유 ID 기반 파일명 생성 (예시)
            unique_id = uuid.uuid4().hex
            final_filename = f"{unique_id}{ext}"

        final_path = os.path.join(save_folder, final_filename)
        os.rename(temp_path, final_path)

        # 썸네일 생성
        thumbnail_name = f"thumb_{final_filename}"
        # THUMBNAIL_FOLDER는 UPLOAD_FOLDER 내부에 있으므로, album_id와 date_path_segment만 추가
        thumbnail_album_date_path = os.path.join(album_id if album_id else "_no_album", date_path_segment)
        thumbnail_save_folder_relative_to_thumb_root = os.path.join(thumbnail_album_date_path)
        thumbnail_save_folder_full = os.path.join(THUMBNAIL_FOLDER, thumbnail_save_folder_relative_to_thumb_root), 
        os.makedirs(thumbnail_save_folder_full, exist_ok=True)
        thumbnail_path_full = os.path.join(thumbnail_save_folder_full, thumbnail_name)
        create_thumbnail(final_path, thumbnail_path_full)

        # DB에 저장할 파일 경로를 항상 '/uploads/...'로 저장
        # 예시: D:/project/album_app/static/uploads/album_name/2023/01/01/image.jpg -> /uploads/album_name/2023/01/01/image.jpg
        db_filepath = final_path.replace(UPLOAD_FOLDER, '').replace('\\', '/').replace('//', '/').lstrip('/')
        db_filepath = '/uploads/' + db_filepath if not db_filepath.startswith('uploads/') else '/' + db_filepath
        db_filepath = db_filepath.replace('//', '/')
        db_thumbnail_filepath = os.path.relpath(thumbnail_path_full, os.path.dirname(UPLOAD_FOLDER)).replace("\\", "/")

        return {
            'id': uuid.uuid4().hex, # 사진 고유 ID
            'filename': final_filename,
            'filepath': db_filepath, # 예: 'uploads/album_name/2023/01/01/image.jpg'
            'thumbnail_filepath': db_thumbnail_filepath, # 예: 'uploads/thumbnails/album_name/2023/01/01/thumb_image.jpg'
            'width': metadata.get('width'),
            'height': metadata.get('height'),
            'taken_at': taken_at,
            'created_date': datetime.now().isoformat(),
            'modified_date': datetime.now().isoformat(),
            'memo': '' # 초기 메모는 비워둠
        }
    except Exception as e:
        current_app.logger.error(f'save_uploaded_file 오류: {str(e)} - 파일: {file.filename if file else "N/A"}', exc_info=True)
        # 임시 파일이 남아있다면 삭제 시도
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as ex_remove:
                current_app.logger.error(f'임시 파일 삭제 오류: {str(ex_remove)}')
        return None

def auto_organize_files(files, album_id=None):
    """
    파일을 자동으로 분류하여 저장하고 메타데이터를 추출합니다.
    
    Args:
        files: 업로드된 파일 객체 리스트
        album_id: 앨범 ID (선택사항)
        
    Returns:
        처리 결과를 포함한 딕셔너리
    """
    try:
        results = {
            'success': True,
            'message': '파일 업로드 완료',
            'saved_files': [],
            'failed_files': []
        }
        
        for file in files:
            if not file or not hasattr(file, 'filename') or not allowed_file(file.filename):
                results['failed_files'].append(getattr(file, 'filename', 'unknown'))
                continue
            try:
                # 파일 저장 및 메타데이터 추출, 촬영일 기준 폴더 저장 및 DB용 정보 반환
                photo_info = save_uploaded_file(file, UPLOAD_FOLDER, album_id, keep_original_name=True)
                if not photo_info:
                    results['failed_files'].append(file.filename)
                    continue
                # DB insert
                if not insert_photo_to_db(photo_info):
                    current_app.logger.error(f"DB 저장 실패: {getattr(file, 'filename', 'unknown')} (Photo ID: {photo_info.get('id')})")
                    results['failed_files'].append(getattr(file, 'filename', 'unknown'))
                    continue
                # 썸네일 경로 계산
                thumbnail_filename = photo_info['filename']
                dt = datetime.fromisoformat(photo_info['taken_at']) if photo_info['taken_at'] else datetime.now()
                date_path = os.path.join(str(dt.year), f"{dt.month:02d}", f"{dt.day:02d}")
                thumbnail_path = os.path.join(THUMBNAIL_FOLDER, date_path, thumbnail_filename)
                # 결과에 추가
                relative_path = os.path.relpath(photo_info['filepath'], start=os.path.dirname(os.path.dirname(UPLOAD_FOLDER)))
                results['saved_files'].append({
                    'original_filename': file.filename,
                    'saved_filename': photo_info['filename'],
                    'path': relative_path.replace('\\', '/'),
                    'thumbnail': os.path.relpath(thumbnail_path, start=os.path.dirname(os.path.dirname(THUMBNAIL_FOLDER))).replace('\\', '/'),
                    'metadata': {
                        'width': photo_info['width'],
                        'height': photo_info['height'],
                        'taken_at': photo_info['taken_at']
                    }
                })
                current_app.logger.info(f"파일 처리 및 DB 저장 완료: {file.filename} -> {photo_info['filepath']}")
            except Exception as e:
                current_app.logger.error(f"파일 처리 중 오류 발생 - {file.filename}: {str(e)}", exc_info=True)
                results['failed_files'].append(file.filename)
        return results
    except Exception as e:
        current_app.logger.error(f'auto_organize_files 오류: {str(e)}', exc_info=True)
        return {
            'success': False,
            'message': f'파일 처리 중 오류가 발생했습니다: {str(e)}',
            'saved_files': [],
            'failed_files': [f.filename for f in files if f and hasattr(f, 'filename')]
        }

@main.route("/")
def home():
    return render_template("main.html")

@main.route("/main_2")
def main_2():
    return render_template("main_2.html")

@main.route("/upload_page")
def upload_page():
    return render_template("upload_page.html")

@main.route('/upload', methods=['POST'])
def upload():
    """
    사진 업로드 처리 및 자동 분류, 데이터베이스 저장
    """
    if 'files[]' not in request.files:
        return jsonify({"success": False, "message": "업로드할 파일이 없습니다."})
    
    files = request.files.getlist('files[]')
    if not files or all(file.filename == '' for file in files):
        return jsonify({"success": False, "message": "선택된 파일이 없습니다."})
    
    try:
        # 앨범 ID 처리 (선택한 경우)
        album_id = request.form.get('album_id', None)
        create_album = request.form.get('createAlbum', 'false').lower() == 'true'
        album_name = request.form.get('albumName', '')
        
        # 새 앨범 생성 요청이 있을 경우
        if create_album and album_name:
            album_id = album_name
        
        # 파일 자동 분류 및 저장 (데이터베이스 포함)
        result = auto_organize_files(files, album_id)
        
        if result['success']:
            saved_count = len(result.get('saved_files', []))
            failed_count = len(result.get('failed_files', []))
            
            message = f"{saved_count}개의 파일이 성공적으로 업로드되었습니다."
            if failed_count > 0:
                message += f" ({failed_count}개 실패)"
            
            return jsonify({
                "success": True,
                "message": message,
                "saved_files": result.get('saved_files', []),
                "failed_files": result.get('failed_files', []),
                "album_id": album_id
            })
        else:
            return jsonify({
                "success": False,
                "message": result.get('message', '파일 업로드 중 오류가 발생했습니다.'),
                "failed_files": result.get('failed_files', [])
            })
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"서버 오류가 발생했습니다: {str(e)}",
            "failed_files": [f.filename for f in files if f and hasattr(f, 'filename')]
        })

@main.route("/image_auto_classify", methods=["POST"])
def image_auto_classify():
    """
    이미지 자동 분류 기능
    """
    if 'files[]' not in request.files:
        return jsonify({"success": False, "message": "업로드할 파일이 없습니다."})
    
    files = request.files.getlist('files[]')
    if not files or all(file.filename == '' for file in files):
        return jsonify({"success": False, "message": "선택된 파일이 없습니다."})
    
    try:
        # 이미지 자동 분류 및 저장
        result = auto_organize_files(files)
        
        # 결과 반환
        response = {
            "success": result['success'],
            "message": result['message']
        }
        
        # 실패한 파일이 있는 경우에만 추가
        if 'failed_files' in result and result['failed_files']:
            response['failed_files'] = result['failed_files']
        
        return jsonify(response)
        
    except Exception as e:
        current_app.logger.error(f'Error in image_auto_classify: {str(e)}')
        return jsonify({"success": False, "message": f"이미지 처리 중 오류가 발생했습니다: {str(e)}"})

@main.route("/main2")
def main2():
    """포토북 스타일의 메인 페이지를 렌더링합니다."""
    return render_template("main_2.html")

@main.route("/photo_list")
def photo_list():
    album_id = request.args.get('album_id', None)
    start_date = request.args.get('start_date', None)
    end_date = request.args.get('end_date', None)
    title = request.args.get('title', None)
    keywords = request.args.get('keywords', None)

    current_album_name = album_id if album_id else "전체 사진"

    # 검색 파라미터를 포함하여 DB에서 사진 정보 목록 조회
    photo_data_list = get_photo_filepaths_by_album_id(
        album_id=album_id,
        start_date=start_date,
        end_date=end_date,
        title=title,
        keywords=keywords
    )

    image_items = []
    all_photo_dates = []
    current_app.logger.info(f"get_photo_filepaths_by_album_id 결과 (photo_data_list): {photo_data_list}")

    for photo_info in photo_data_list:
        db_filepath = photo_info.get('filepath')
        taken_at_str = photo_info.get('date')

        if not db_filepath or not taken_at_str:
            current_app.logger.warning(f"사진 정보에 filepath 또는 date가 누락되었습니다: {photo_info}")
            continue

        # 파일 경로를 URL로 변환 (Windows 경로 '\'를 '/'로 변경)
        # 저장된 경로는 'album_name/YYYY/MM/DD/filename.jpg' 또는 'YYYY/MM/DD/filename.jpg' 형태를 가정
        normalized_db_path = db_filepath.replace('\\', '/')
        
        # URL은 '/static/uploads/...' 형태를 따름 (사용자 메모리에 따라 향후 /uploads/... 직접 서비스 고려)
        if not normalized_db_path.startswith('uploads/'):
            # 'uploads/' 접두사가 없는 경우, 경로가 앨범명부터 시작하거나 날짜부터 시작하는 경우를 포괄하기 위함
            # 예: 'MyAlbum/2023/01/01/img.jpg' -> 'uploads/MyAlbum/2023/01/01/img.jpg'
            # 예: '2023/01/01/img.jpg' -> 'uploads/2023/01/01/img.jpg'
            # 이미 'uploads/'로 시작하는 경우엔 이 부분을 건너뜀
            test_path_parts = normalized_db_path.split('/')
            if len(test_path_parts) > 1 and test_path_parts[0].lower() != 'uploads': # 이미 uploads로 시작하지 않는 경우
                 # uploads/가 없는 경우, 그리고 첫번째 디렉토리명이 uploads가 아닌 경우
                normalized_db_path = 'uploads/' + normalized_db_path.lstrip('/') 
            elif len(test_path_parts) == 1 and test_path_parts[0].lower() != 'uploads': # 파일명만 있는 경우 (uploads/filename.jpg)
                normalized_db_path = 'uploads/' + normalized_db_path.lstrip('/')
        
        # 최종적으로 'uploads/'로 시작하지 않으면 경고 후 강제 추가 (최후의 방어 로직)
        if not normalized_db_path.startswith('uploads/'):
            current_app.logger.warning(f"DB filepath '{db_filepath}'가 'uploads/'로 시작하지 않아 강제로 추가합니다: {normalized_db_path}")
            normalized_db_path = 'uploads/' + normalized_db_path.lstrip('/')

        image_url = '/static/' + normalized_db_path
        
        # 날짜 문자열 (예: YYYY-MM-DDTHH:MM:SS 또는 YYYY-MM-DD HH:MM:SS)에서 날짜 부분(YYYY-MM-DD)만 추출
        if 'T' in taken_at_str:
            display_date = taken_at_str.split('T')[0]
        else:
            display_date = taken_at_str.split(' ')[0]
        
        keywords = photo_info.get('keywords', '') # 키워드가 없을 경우 빈 문자열
        image_items.append({'url': image_url, 'date': display_date, 'keywords': keywords})
        all_photo_dates.append(display_date)

    # 사진 기간 문자열 생성
    photo_date_range_str = ""
    if all_photo_dates:
        min_date = min(all_photo_dates)
        max_date = max(all_photo_dates)
        if min_date == max_date:
            photo_date_range_str = min_date
        else:
            photo_date_range_str = f"{min_date} ~ {max_date}"
    else:
        photo_date_range_str = "날짜 정보 없음"

    current_app.logger.info(f"photo_list 템플릿으로 전달되는 image_items: {image_items}")
    return render_template("photo_list.html", 
                           current_album_name=current_album_name, 
                           image_items_json=json.dumps(image_items),
                           photo_date_range=photo_date_range_str,
                           search_params={
                               'album_id': album_id if album_id else '',
                               'start_date': start_date if start_date else '',
                               'end_date': end_date if end_date else '',
                               'title': title if title else '',
                               'keywords': keywords if keywords else ''
                           }
                           )

@main.route('/photo_list_2')
def photo_list_2():
    album_id = request.args.get('album_id', None)
    start_date = request.args.get('start_date', None)
    end_date = request.args.get('end_date', None)
    title = request.args.get('title', None)
    keywords = request.args.get('keywords', None)

    current_album_name = album_id if album_id else "전체 사진"

    # 검색 파라미터를 포함하여 DB에서 사진 정보 목록 조회
    photo_data_list = get_photo_filepaths_by_album_id(
        album_id=album_id,
        start_date=start_date,
        end_date=end_date,
        title=title,
        keywords=keywords
    )

    image_items = []
    all_photo_dates = []
    current_app.logger.info(f"get_photo_filepaths_by_album_id 결과 (photo_data_list): {photo_data_list}")

    for photo_info in photo_data_list:
        db_filepath = photo_info.get('filepath')
        taken_at_str = photo_info.get('date')

        if not db_filepath or not taken_at_str:
            current_app.logger.warning(f"사진 정보에 filepath 또는 date가 누락되었습니다: {photo_info}")
            continue

        # 파일 경로를 URL로 변환 (Windows 경로 '\'를 '/'로 변경)
        # 저장된 경로는 'album_name/YYYY/MM/DD/filename.jpg' 또는 'YYYY/MM/DD/filename.jpg' 형태를 가정
        normalized_db_path = db_filepath.replace('\\', '/')
        
        # URL은 '/static/uploads/...' 형태를 따름 (사용자 메모리에 따라 향후 /uploads/... 직접 서비스 고려)
        if not normalized_db_path.startswith('uploads/'):
            # 'uploads/' 접두사가 없는 경우, 경로가 앨범명부터 시작하거나 날짜부터 시작하는 경우를 포괄하기 위함
            # 예: 'MyAlbum/2023/01/01/img.jpg' -> 'uploads/MyAlbum/2023/01/01/img.jpg'
            # 예: '2023/01/01/img.jpg' -> 'uploads/2023/01/01/img.jpg'
            # 이미 'uploads/'로 시작하는 경우엔 이 부분을 건너뜀
            test_path_parts = normalized_db_path.split('/')
            if len(test_path_parts) > 1 and test_path_parts[0].lower() != 'uploads': # 이미 uploads로 시작하지 않는 경우
                 # uploads/가 없는 경우, 그리고 첫번째 디렉토리명이 uploads가 아닌 경우
                normalized_db_path = 'uploads/' + normalized_db_path.lstrip('/') 
            elif len(test_path_parts) == 1 and test_path_parts[0].lower() != 'uploads': # 파일명만 있는 경우 (uploads/filename.jpg)
                normalized_db_path = 'uploads/' + normalized_db_path.lstrip('/')
        
        # 최종적으로 'uploads/'로 시작하지 않으면 경고 후 강제 추가 (최후의 방어 로직)
        if not normalized_db_path.startswith('uploads/'):
            current_app.logger.warning(f"DB filepath '{db_filepath}'가 'uploads/'로 시작하지 않아 강제로 추가합니다: {normalized_db_path}")
            normalized_db_path = 'uploads/' + normalized_db_path.lstrip('/')

        image_url = '/static/' + normalized_db_path
        
        # 날짜 문자열 (예: YYYY-MM-DDTHH:MM:SS 또는 YYYY-MM-DD HH:MM:SS)에서 날짜 부분(YYYY-MM-DD)만 추출
        if 'T' in taken_at_str:
            display_date = taken_at_str.split('T')[0]
        else:
            display_date = taken_at_str.split(' ')[0]
        
        keywords = photo_info.get('keywords', '') # 키워드가 없을 경우 빈 문자열
        image_items.append({'url': image_url, 'date': display_date, 'keywords': keywords})
        all_photo_dates.append(display_date)

    # 사진 기간 문자열 생성
    photo_date_range_str = ""
    if all_photo_dates:
        min_date = min(all_photo_dates)
        max_date = max(all_photo_dates)
        if min_date == max_date:
            photo_date_range_str = min_date
        else:
            photo_date_range_str = f"{min_date} ~ {max_date}"
    else:
        photo_date_range_str = "날짜 정보 없음"

    current_app.logger.info(f"photo_list 템플릿으로 전달되는 image_items: {image_items}")
    return render_template("photo_list_2.html", 
                           current_album_name=current_album_name, 
                           image_items_json=json.dumps(image_items),
                           photo_date_range=photo_date_range_str,
                           search_params={
                               'album_id': album_id if album_id else '',
                               'start_date': start_date if start_date else '',
                               'end_date': end_date if end_date else '',
                               'title': title if title else '',
                               'keywords': keywords if keywords else ''
                           }
                           )