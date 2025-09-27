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

    if request.method == "POST":
        try:
            # Extract video file from request
            video_file = request.FILES.get("video_file")

            if not video_file:
                context["error_message"] = (
                    "No video file was uploaded. Please select a file."
                )
                return render(request, "video_upload.html", context)

            # Validate file type
            if not video_file.content_type.startswith("video/"):
                context["error_message"] = (
                    "Invalid file type. Please upload a video file."
                )
                return render(request, "video_upload.html", context)

            # Validate file size (100MB limit)
            max_size = 100 * 1024 * 1024  # 100MB in bytes
            if video_file.size > max_size:
                context["error_message"] = "File too large. Maximum size is 100MB."
                return render(request, "video_upload.html", context)

            # Save the video file temporarily or permanently
            video_path = ...

            # Process the video (replace this with your actual processing logic)
            processing_result = ...

        except Exception as e:
            context["error_message"] = f"Error processing video: {str(e)}"

    return render(request, "web/video_upload.html", context)
