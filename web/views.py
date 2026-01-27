import os
import tempfile
import base64
import requests

from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from requests.exceptions import RequestException, Timeout


API_URL = "https://rppg-server-pack.onrender.com/upload_video"

# Set this to True only if you REALLY want video preview (base64 can be huge on Render)
ENABLE_PREVIEW = False
MAX_PREVIEW_MB = 3  # only used if ENABLE_PREVIEW=True


@csrf_protect
def video_upload_view(request):
    context = {}

    if request.method == "POST":
        temp_file_path = None

        try:
            video_file = request.FILES.get("video_file")

            if not video_file:
                context["error_message"] = "No video file was uploaded."
                return render(request, "web/video_upload.html", context)

            if not (video_file.content_type or "").startswith("video/"):
                context["error_message"] = "Invalid file type."
                return render(request, "web/video_upload.html", context)

            if video_file.size > 100 * 1024 * 1024:
                context["error_message"] = "File too large (max 100MB)."
                return render(request, "web/video_upload.html", context)

            # 1) Read metadata from the HTML form (POST)
            subject_id = (request.POST.get("subject_id", "S01") or "S01").strip()
            condition  = (request.POST.get("condition", "rest") or "rest").strip().lower()
            modality   = (request.POST.get("modality", "face") or "face").strip().lower()
            method     = (request.POST.get("method", "thesis_precomputed") or "thesis_precomputed").strip()

            # 2) Optional: auto-detect from filename if user left defaults
            name_lower = (video_file.name or "").lower()

            # If user forgot and left "rest", let filename override
            if condition == "rest":
                if "breath" in name_lower:
                    condition = "breath"
                elif "exercise" in name_lower:
                    condition = "exercise"
                elif "rest" in name_lower:
                    condition = "rest"

            # If user forgot and left "face", let filename override
            if modality == "face":
                if "palm" in name_lower:
                    modality = "palm"
                elif "face" in name_lower:
                    modality = "face"

            # Helpful logs (shows exact upload time in Render Logs)
            print(f"[UPLOAD] name={video_file.name} size={video_file.size} type={video_file.content_type}")
            print(f"[META] subject={subject_id} condition={condition} modality={modality} method={method}")

            # Save temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                for chunk in video_file.chunks():
                    tmp.write(chunk)
                temp_file_path = tmp.name

            # ---- CALL API ----
            with open(temp_file_path, "rb") as f:
                files = {"file": (video_file.name, f, video_file.content_type)}

                data = {
                    "subject_id": subject_id,
                    "condition": condition,
                    "modality": modality,
                    "method": method,
                    "min_valid_pct": 50,
                    "save": 0,
                    "timeout_sec": 120,
                }

                print("[API] sending request...")
                response = requests.post(API_URL, files=files, data=data, timeout=130)
                print(f"[API] status={response.status_code}")
                response.raise_for_status()
                rppg_result = response.json()
            # -------------------

            # Cleanup temp file
            os.unlink(temp_file_path)
            temp_file_path = None

            # Video preview (DISABLED by default to avoid huge HTML response)
            video_data_url = None
            if ENABLE_PREVIEW:
                # Only preview small files
                if video_file.size <= MAX_PREVIEW_MB * 1024 * 1024:
                    with open(temp_file_path, "rb") as vf:
                        video_content = vf.read()
                    video_base64 = base64.b64encode(video_content).decode("utf-8")
                    video_data_url = f"data:{video_file.content_type};base64,{video_base64}"

            context.update({
                "video_data": {
                    "name": video_file.name,
                    "size": video_file.size,
                    "content_type": video_file.content_type,
                },
                "video_data_url": video_data_url,   # can be None
                "p_result": rppg_result,
                "p_status": "completed",
                "success_msg": "Video uploaded and analyzed successfully!"
            })

        except Timeout:
            context["error_message"] = "API request timed out. Try a smaller/shorter video or retry."
        except RequestException as e:
            context["error_message"] = f"API request failed: {str(e)}"
        except Exception as e:
            context["error_message"] = str(e)

        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    return render(request, "web/video_upload.html", context)
