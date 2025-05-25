from flask import Flask, request, send_file
import os
import subprocess
import uuid

UPLOAD_DIR = "/tmp"
FONT_PATH = "static/Inter-ExtraLight.ttf"
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
    edited_filename = f"edited_{uuid.uuid4()}.mp4"
    raw_path = os.path.join(UPLOAD_DIR, raw_filename)
    edited_path = os.path.join(UPLOAD_DIR, edited_filename)

    file.save(raw_path)

    drawtext = (
        f"drawtext=fontfile={FONT_PATH}:"
        f"text='{caption}':"
        f"fontcolor=black:fontsize=48:x=(w-text_w)/2:y=40"
    )

    vf_filters = (
        f"scale=iw:iw,"
        f"pad={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:(ow-iw)/2:(oh-ih)/2:white,"
        f"{drawtext}"
    )

    try:
        cmd = [
            "ffmpeg", "-i", raw_path,
            "-vf", vf_filters,
            "-c:a", "copy",
            "-preset", "ultrafast",
            "-y", edited_path
        ]
        subprocess.run(cmd, check=True)
        return send_file(edited_path, mimetype='video/mp4')

    except Exception as e:
        return {"error": str(e)}, 500
    finally:
        if os.path.exists(raw_path): os.remove(raw_path)
        if os.path.exists(edited_path): os.remove(edited_path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
