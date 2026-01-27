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

        try:
            video_file = request.FILES.get("video_file")

            if not video_file:
                context["error_message"] = "No video file was uploaded."
                return render(request, "web/video_upload.html", context)

            if not video_file.content_type.startswith("video/"):
                context["error_message"] = "Invalid file type."
                return render(request, "web/video_upload.html", context)

            if video_file.size > 100 * 1024 * 1024:
                context["error_message"] = "File too large (max 100MB)."
                return render(request, "web/video_upload.html", context)

            # Save temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                for chunk in video_file.chunks():
                    tmp.write(chunk)
                temp_file_path = tmp.name

            # ---- READ METADATA FROM HTML FORM (POST) ----
            subject_id = (request.POST.get("subject_id", "S01") or "S01").strip()
            condition = (request.POST.get("condition", "rest") or "rest").strip().lower()
            modality = (request.POST.get("modality", "face") or "face").strip().lower()
            method = (
                request.POST.get("method", "thesis_precomputed") or "thesis_precomputed"
            ).strip()

            # ---- OPTIONAL: AUTO-DETECT FROM FILENAME ----
            name_lower = (video_file.name or "").lower()

            # only override condition if filename contains a known tag
            if "breath" in name_lower:
                condition = "breath"
            elif "exercise" in name_lower:
                condition = "exercise"
            elif "rest" in name_lower:
                condition = "rest"

            # only override modality if filename contains a known tag
            if "palm" in name_lower:
                modality = "palm"
            elif "face" in name_lower:
                modality = "face"

            # ---- CALL YOUR THESIS API ----
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

                response = requests.post(API_URL, files=files, data=data, timeout=130)
                response.raise_for_status()
                rppg_result = response.json()
            # ----------------------------

            # Cleanup temp file
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                temp_file_path = None

            # Video preview (IMPORTANT: reset pointer before reading)
            video_file.seek(0)
            video_content = video_file.read()

            video_base64 = base64.b64encode(video_content).decode("utf-8")
            video_data_url = f"data:{video_file.content_type};base64,{video_base64}"

            context.update(
                {
                    "video_data": {
                        "name": video_file.name,
                        "size": video_file.size,
                        "content_type": video_file.content_type,
                    },
                    "video_data_url": video_data_url,
                    "p_result": rppg_result,
                    "p_status": "completed",
                    "success_msg": "Video uploaded and analyzed successfully!",
                }
            )

        except Exception as e:
            context["error_message"] = str(e)

        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    pass

    return render(request, "web/video_upload.html", context)
