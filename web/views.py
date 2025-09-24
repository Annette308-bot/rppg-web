import os
import tempfile
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import mimetypes

@csrf_protect
def video_upload_view(request):
    context = {}
    
    if request.method == 'POST':
        try:
            # Extract video file from request
            video_file = request.FILES.get('video_file')
            
            if not video_file:
                context['error_message'] = 'No video file was uploaded. Please select a file.'
                return render(request, 'video_upload.html', context)
            
            # Validate file type
            if not video_file.content_type.startswith('video/'):
                context['error_message'] = 'Invalid file type. Please upload a video file.'
                return render(request, 'video_upload.html', context)
            
            # Validate file size (100MB limit)
            max_size = 100 * 1024 * 1024  # 100MB in bytes
            if video_file.size > max_size:
                context['error_message'] = 'File too large. Maximum size is 100MB.'
                return render(request, 'video_upload.html', context)
            
            # Save the video file temporarily or permanently
            video_path = handle_uploaded_video(video_file)
            
            # Process the video (replace this with your actual processing logic)
            processing_result = process_video(video_path, video_file)
            
            # Prepare context for template
            context.update({
                'video_data': video_file,
                'video_url': get_video_url(video_path),
                'processing_status': 'completed',  # or 'processing', 'error'
                'processing_result': processing_result,
                'success_message': 'Video uploaded and processed successfully!',
                'video_duration': get_video_duration(video_path),  # Optional
            })
            
        except Exception as e:
            context['error_message'] = f'Error processing video: {str(e)}'
    
    return render(request, 'web/video_upload.html', context)


def handle_uploaded_video(video_file):
    """
    Handle the uploaded video file - save it and return the path
    """
    # Create a unique filename
    filename = f"{video_file.name}"
    
    # Save to media directory or temporary location
    if hasattr(settings, 'MEDIA_ROOT'):
        # Save to media directory (permanent storage)
        file_path = default_storage.save(f'videos/{filename}', ContentFile(video_file.read()))
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    else:
        # Save to temporary directory
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp_file:
            for chunk in video_file.chunks():
                tmp_file.write(chunk)
            full_path = tmp_file.name
    
    return full_path


def process_video(video_path, video_file):
    """
    Process the video file - replace this with your actual processing logic
    """
    try:
        # Here's where you'd implement your video processing logic
        # This could include:
        # - Video analysis using OpenCV, FFmpeg, etc.
        # - Machine learning inference
        # - Format conversion
        # - Thumbnail generation
        # - Metadata extraction
        
        # Example processing result structure
        result = {
            'analysis': 'Video analysis completed successfully. Detected motion patterns and key frames.',
            'metadata': {
                'resolution': '1920x1080',  # Extract from actual video
                'framerate': '30 fps',      # Extract from actual video
                'codec': 'H.264',           # Extract from actual video
                'bitrate': '5000 kbps',     # Extract from actual video
            },
            'processed_video_url': None,  # URL to processed video if applicable
        }
        
        # Example: Extract basic metadata using file properties
        file_stats = os.stat(video_path)
        result['metadata'].update({
            'file_size': video_file.size,
            'upload_time': file_stats.st_mtime,
        })
        
        return result
        
    except Exception as e:
        return {
            'error': str(e),
            'analysis': 'Processing failed due to an error.',
        }


def get_video_url(video_path):
    """
    Get the URL for serving the video file
    """
    if hasattr(settings, 'MEDIA_URL') and hasattr(settings, 'MEDIA_ROOT'):
        # For permanent media files
        relative_path = os.path.relpath(video_path, settings.MEDIA_ROOT)
        return f"{settings.MEDIA_URL}{relative_path}"
    else:
        # For temporary files, you might need a different approach
        # This is a simplified example - in production, you'd want proper file serving
        return f"/media/temp/{os.path.basename(video_path)}"


def get_video_duration(video_path):
    """
    Extract video duration - optional feature
    You can use libraries like moviepy, opencv, or ffmpeg-python
    """
    try:
        # Example using moviepy (install with: pip install moviepy)
        # from moviepy.editor import VideoFileClip
        # clip = VideoFileClip(video_path)
        # duration = clip.duration
        # clip.close()
        # return f"{int(duration // 60)}:{int(duration % 60):02d}"
        
        # Placeholder return
        return "2:34"  # Replace with actual duration extraction
        
    except Exception:
        return None


# Optional: Add a separate view for serving processed videos
def serve_video(request, video_path):
    """
    Serve video files - for development only
    In production, use a proper web server (nginx/apache) to serve media files
    """
    try:
        with open(video_path, 'rb') as video_file:
            content_type, _ = mimetypes.guess_type(video_path)
            response = HttpResponse(video_file.read(), content_type=content_type or 'video/mp4')
            response['Content-Disposition'] = f'inline; filename="{os.path.basename(video_path)}"'
            return response
    except Exception as e:
        return HttpResponse(f'Error serving video: {str(e)}', status=404)