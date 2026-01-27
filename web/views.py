import requests
import os
import tempfile
import base64
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect


@csrf_protect
def video_upload_view(request):
    context = {}

    if request.method == "POST":
        temp_file_path = None
        try:
            video_file = request.FILES.get("video_file")

            if not video_file:
                context["error_message"] = "No video file was uploaded. Please select a file."
                return render(request, "web/video_upload.html", context)

            if not (video_file.content_type or "").startswith("video/"):
                context["error_message"] = "Invalid file type. Please upload a video file."
                return render(request, "web/video_upload.html", context)

            max_size = 100 * 1024 * 1024
            if video_file.size > max_size:
                context["error_message"] = "File too large. Maximum size is 100MB."
                return render(request, "web/video_upload.html", context)

            # Read uploaded bytes
            video_file.seek(0)
            video_content = video_file.read()

            # Save to a temp file (so requests can stream it)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
                temp_file.write(video_content)
                temp_file_path = temp_file.name

            # ---- Call your Render API ----
            API_URL = "https://rppg-server-pack.onrender.com/upload_video"

            # Optional: take these from your HTML form if you add them
            subject_id = request.POST.get("subject_id", "S01")
            condition = request.POST.get("condition", "rest")   # rest / breath / exercise
            modality = request.POST.get("modality", "face")     # face / palm

            data = {
                "subject_id": subject_id,
                "condition": condition,
                "modality": modality,
                "method": "thesis_precomputed",
                "min_valid_pct": 50,
                "save": 0,
                "timeout_sec": 120,
            }

            with open(temp_file_path, "rb") as f:
                files = {
                    "file": (video_file.name, f, video_file.content_type or "video/mp4")
                }
                response = requests.post(API_URL, files=files, data=data, timeout=130)

            response.raise_for_status()
            rppg_result = response.json()
            # -----------------------------

            # cleanup temp file early
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                    temp_file_path = None
                except OSError:
                    pass

            # For preview (optional)
            video_base64 = base64.b64encode(video_content).decode("utf-8")
            video_data_url = f"data:{video_file.content_type};base64,{video_base64}"

            context.update(
                {
                    "video_data": {
                        "name": video_file.name,
                        "size": video_file.size,
                        "content_type": video_file.content_type,
                    },
                    "analysis": "Video processing completed successfully.",
                    "video_data_url": video_data_url,
                    "p_result": rppg_result,
                    "p_status": "completed" if rppg_result.get("ok") else "failed",
                    "success_msg": "Video uploaded and processed successfully!",
                }
            )

        except Exception as e:
            context["error_message"] = f"Error processing video: {str(e)}"

        finally:
            # final safety cleanup
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    pass

    return render(request, "web/video_upload.html", context)
