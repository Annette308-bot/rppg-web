import os
import tempfile
import base64
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from .rppg import process_video


def process_video_test(video_path):
    """
    Process the video file and return analysis results.
    Replace this with your actual video processing logic.
    """
    try:
        # Placeholder for your video processing logic
        # This could include:
        # - RPPG analysis
        # - Face detection
        # - Heart rate extraction
        # - Other video analysis

        # For now, returning mock data
        result = {
            "analysis": "Video processing completed successfully. Heart rate patterns detected.",
            "meta": {
                "frames_processed": 1500,
                "avg_heart_rate": "72 BPM",
                "confidence_score": "95%",
                "processing_time": "45 seconds",
            },
            "status": "completed",
        }

        return result
    except Exception as e:
        return {"status": "error", "error_message": str(e)}


@csrf_protect
def video_upload_view(request):
    context = {}

    if request.method == "POST":
        temp_file_path = None
        try:
            video_file = request.FILES.get("video_file")

            if not video_file:
                context["error_message"] = (
                    "No video file was uploaded. Please select a file."
                )
                return render(request, "web/video_upload.html", context)

            if not video_file.content_type.startswith("video/"):
                context["error_message"] = (
                    "Invalid file type. Please upload a video file."
                )
                return render(request, "web/video_upload.html", context)

            max_size = 100 * 1024 * 1024
            if video_file.size > max_size:
                context["error_message"] = "File too large. Maximum size is 100MB."
                return render(request, "web/video_upload.html", context)

            video_file.seek(0)
            video_content = video_file.read()

            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
                temp_file.write(video_content)
                temp_file_path = temp_file.name

            rppg_result = process_video(temp_file_path)
            rppg_result.pop("file")

            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                    temp_file_path = None  # Mark as deleted
                except OSError:
                    pass

            video_base64 = base64.b64encode(video_content).decode("utf-8")
            video_data_url = f"data:{video_file.content_type};base64,{video_base64}"

            context.update(
                {
                    "video_data": {
                        "name": video_file.name,
                        "size": video_file.size,
                        "content_type": video_file.content_type,
                    },"analysis": "Video processing completed successfully. Heart rate patterns detected.",
                    "video_data_url": video_data_url,
                    "p_result": rppg_result,
                    "p_status": rppg_result.get("status", "completed"),
                    "success_msg": "Video uploaded and processed successfully!",
                }
            )

        except Exception as e:
            context["error_message"] = f"Error processing video: {str(e)}"

        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    pass

    return render(request, "web/video_upload.html", context)
