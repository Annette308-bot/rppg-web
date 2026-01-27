import os
import tempfile
import base64
import requests

from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect


API_URL = "https://rppg-server-pack.onrender.com/upload_video"


@csrf_protect
def video_upload_view(request):
    context = {}

    if request.method == "POST":
        temp_file_path = None
        file_handle = None

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

            # Read uploaded bytes (for preview)
            video_file.seek(0)
            video_content = video_file.read()

            # Save to a temporary file (so we can send it to the API)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                tmp.write(video_content)
                temp_file_path = tmp.name

            # Use defaults (you can later add form fields in HTML if you want)
            subject_id = request.POST.get("subject_id", "S01")
            condition = request.POST.get("condition", "rest")   # rest / breath / exercise
            modality = request.POST.get("modality", "face")     # face / palm

            # Call your FastAPI thesis server
            file_handle = open(temp_file_path, "rb")
            files = {
                "file": (video_file.name, file_handle, video_file.content_type or "video/mp4")
            }
            data = {
                "subject_id": subject_id,
                "condition": condition,
                "modality": modality,
                "method": "thesis_precomputed",
                "min_valid_pct": 50,
                "save": 0,
                "timeout_sec": 120,
            }

            resp = requests.post(API_URL, files=files, data=data, timeout=140)
            resp.raise_for_status()
            rppg_result = resp.json()

            # Close file handle
            try:
                file_handle.close()
                file_handle = None
            except Exception:
                pass

            # Delete temp file
            try:
                os.unlink(temp_file_path)
                temp_file_path = None
            except Exception:
                pass

            # Preview video in browser (optional)
            video_base64 = base64.b64encode(video_content).decode("utf-8")
            video_data_url = f"data:{video_file.content_type};base64,{video_base64}"

            context.update(
                {
                    "video_data": {
                        "name": video_file.name,
                        "size": video_file.size,
                        "content_type": video_file.content_type,
                    },
                    "analysis": "Video processed using the thesis pipeline API.",
                    "video_data_url": video_data_url,
                    "p_result": rppg_result,
                    "p_status": "completed" if rppg_result.get("ok") == 1 else "error",
                    "success_msg": "Video uploaded and analyzed successfully!",
                }
            )

        except requests.exceptions.RequestException as e:
            context["error_message"] = f"API request failed: {str(e)}"

        except Exception as e:
            context["error_message"] = f"Error processing video: {str(e)}"

        finally:
            # Safety cleanup
            if file_handle is not None:
                try:
                    file_handle.close()
                except Exception:
                    pass

            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    pass

    return render(request, "web/video_upload.html", context)
