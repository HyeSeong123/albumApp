from flask import Blueprint, render_template, request, jsonify, current_app
import os
from datetime import datetime
import shutil
from werkzeug.utils import secure_filename
from PIL import Image, ExifTags
import hashlib
import uuid

# DB insert 함수 임포트
from py_sources.models.photo_repository import PhotoDateExtractor, insert_photo_to_db

main = Blueprint("main", __name__)

# 업로드 폴더 설정
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 썸네일 폴더 설정
THUMBNAIL_FOLDER = os.path.join(UPLOAD_FOLDER, 'thumbnails')
if not os.path.exists(THUMBNAIL_FOLDER):
    os.makedirs(THUMBNAIL_FOLDER)

# 허용되는 이미지 확장자
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_hash(file_data):
    """파일의 해시값 계산 (중복 파일 검출용)"""
    file_data.seek(0)  # 파일 포인터를 처음으로 되돌림
    file_hash = hashlib.md5(file_data.read()).hexdigest()
    file_data.seek(0)  # 파일 포인터를 다시 처음으로 되돌림
    return file_hash

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
        date_path = os.path.join(str(dt.year), f"{dt.month:02d}", f"{dt.day:02d}")
        save_folder = os.path.join(base_folder, date_path)
        os.makedirs(save_folder, exist_ok=True)
        new_filename = f"{name}_{int(dt.timestamp())}{ext.lower()}"
        filepath = os.path.join(save_folder, new_filename)
        os.rename(temp_path, filepath)
        # 이미지 처리
        if ext.lower() in {'.jpg', '.jpeg'}:
            fix_image_orientation(filepath)
        thumbnail_folder = os.path.join(THUMBNAIL_FOLDER, date_path)
        os.makedirs(thumbnail_folder, exist_ok=True)
        thumbnail_path = os.path.join(thumbnail_folder, new_filename)
        create_thumbnail(filepath, thumbnail_path)
        # DB 저장용 정보 반환
        return {
            'id': str(uuid.uuid4()),
            'album_id': album_id,
            'filename': new_filename,
            'filepath': filepath,
            'width': metadata.get('width'),
            'height': metadata.get('height'),
            'taken_at': taken_at,
            'memo': ''
        }
    except Exception as e:
        current_app.logger.error(f'파일 처리 중 오류 발생: {str(e)}', exc_info=True)
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
    return render_template("main.html", message="test")

@main.route("/upload_page")
def upload_page():
    return render_template("upload_page.html", message="test")

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
            from uuid import uuid4
            album_id = f"album_{uuid4().hex[:8]}"
        
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
