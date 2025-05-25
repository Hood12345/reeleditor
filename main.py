from flask import Flask, request, send_file
import os
import subprocess
import uuid
import json

UPLOAD_DIR = "/tmp"
FONT_PATH = "static/Inter_18pt-ExtraLight.ttf"
OUTPUT_WIDTH = 720
OUTPUT_HEIGHT = 1280

app = Flask(__name__)

@app.route('/edit', methods=['POST'])
def edit_video():
    if 'file' not in request.files or 'caption' not in request.form:
        return {'error': 'Missing file or caption'}, 400

    file = request.files['file']
    caption = request.form['caption']

    raw_filename = f"raw_{uuid.uuid4()}.mp4"
    cropped_filename = f"cropped_{uuid.uuid4()}.mp4"
    edited_filename = f"edited_{uuid.uuid4()}.mp4"
    raw_path = os.path.join(UPLOAD_DIR, raw_filename)
    cropped_path = os.path.join(UPLOAD_DIR, cropped_filename)
    edited_path = os.path.join(UPLOAD_DIR, edited_filename)

    file.save(raw_path)

    try:
        # Step 1: Detect crop area
        cropdetect_cmd = [
            "ffmpeg", "-i", raw_path,
            "-t", "2", "-vf", "cropdetect=24:16:0",
            "-f", "null", "-"
        ]
        result = subprocess.run(cropdetect_cmd, capture_output=True, text=True)

        # Extract crop parameters from log
        crop_lines = [line for line in result.stderr.split('\n') if "crop=" in line]
        crop_values = [line.split("crop=")[-1].strip() for line in crop_lines if "crop=" in line]
        crop_filter = crop_values[-1] if crop_values else None

        if not crop_filter:
            raise Exception("Failed to detect crop area")

        # Step 2: Crop the video to content area
        crop_cmd = [
            "ffmpeg", "-i", raw_path,
            "-vf", f"crop={crop_filter}",
            "-c:a", "copy", "-y", cropped_path
        ]
        subprocess.run(crop_cmd, check=True)

        # Step 3: Resize to fit inside 720x720 while preserving aspect ratio and detect height for caption
        scale_probe_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json", cropped_path
        ]
        probe_result = subprocess.run(scale_probe_cmd, capture_output=True, text=True)
        dimensions = json.loads(probe_result.stdout)
        original_width = dimensions['streams'][0]['width']
        original_height = dimensions['streams'][0]['height']

        scale_factor = min(OUTPUT_WIDTH / original_width, OUTPUT_WIDTH / original_height)
        scaled_height = int(original_height * scale_factor)

        # Step 4: Pad to 720x1280 and overlay caption just above video
        caption_y = int((OUTPUT_HEIGHT - scaled_height) / 2) - 60
        caption_y = max(caption_y, 20)

        drawtext = (
            f"drawtext=fontfile='{FONT_PATH}':text='{caption}':"
            f"fontcolor=black:fontsize=48:x=(w-text_w)/2:y={caption_y}"
        )

        vf_filters = (
            f"scale='min(iw,{OUTPUT_WIDTH})':'min(ih,{OUTPUT_WIDTH})':force_original_aspect_ratio=decrease,"  # Fit inside square
            f"pad={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:(ow-iw)/2:(oh-ih)/2:white,"  # Center inside 720x1280
            f"{drawtext}"
        )

        final_cmd = [
            "ffmpeg", "-i", cropped_path,
            "-vf", vf_filters,
            "-c:a", "copy",
            "-preset", "ultrafast",
            "-y", edited_path
        ]
        subprocess.run(final_cmd, check=True)

        return send_file(edited_path, mimetype='video/mp4')

    except Exception as e:
        return {"error": str(e)}, 500
    finally:
        for path in [raw_path, cropped_path, edited_path]:
            if os.path.exists(path):
                os.remove(path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
