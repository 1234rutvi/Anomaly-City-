%%writefile anomaly-city/app.py

from flask import Flask, render_template, request, jsonify
import os
import uuid
import pandas as pd

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(__file__),
    "uploads"
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "csv", "xlsx", "xls", "json", "txt", "pdf"
}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def parse_uploaded_file(filepath, extension):

    if extension == "csv":
        return pd.read_csv(filepath), "tabular"

    if extension in ["xlsx", "xls"]:
        return pd.read_excel(filepath), "tabular"

    if extension == "json":
        try:
            return pd.read_json(filepath), "tabular"
        except Exception:
            import json

            with open(
                filepath,
                "r",
                encoding="utf-8"
            ) as f:
                content = json.load(f)

            return pd.json_normalize(content), "tabular"

    if extension == "txt":
        with open(
            filepath,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as f:
            lines = [
                line.strip()
                for line in f
                if line.strip()
            ]

        return pd.DataFrame({
            "text": lines
        }), "text"

    if extension == "pdf":

        from pypdf import PdfReader

        reader = PdfReader(filepath)

        pages = []

        for page in reader.pages:
            text = page.extract_text()

            if text:
                pages.append(text)

        full_text = "\n".join(pages)

        if not full_text.strip():
            raise ValueError(
                "No readable text was found in this PDF."
            )

        lines = [
            line.strip()
            for line in full_text.splitlines()
            if line.strip()
        ]

        return pd.DataFrame({
            "text": lines
        }), "text"

    raise ValueError("Unsupported file type.")


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({
        "success": True,
        "application": "Anomaly City",
        "status": "running"
    })


@app.route("/upload", methods=["POST"])
def upload():

    try:

        if "file" not in request.files:
            return jsonify({
                "success": False,
                "error": "No file was received."
            }), 400

        file = request.files["file"]

        if not file.filename:
            return jsonify({
                "success": False,
                "error": "No file was selected."
            }), 400

        filename = file.filename

        if not allowed_file(filename):
            return jsonify({
                "success": False,
                "error": (
                    "Unsupported file type. "
                    "Use CSV, Excel, JSON, TXT or PDF."
                )
            }), 400

        extension = filename.rsplit(
            ".", 1
        )[1].lower()

        unique_filename = (
            str(uuid.uuid4())
            + "."
            + extension
        )

        filepath = os.path.join(
            app.config["UPLOAD_FOLDER"],
            unique_filename
        )

        file.save(filepath)

        df, data_type = parse_uploaded_file(
            filepath,
            extension
        )

        if df is None:
            raise ValueError(
                "The file could not be converted into a dataset."
            )

        df.columns = [
            str(column).strip()
            for column in df.columns
        ]

        rows = int(len(df))

        columns = int(len(df.columns))

        missing = int(
            df.isnull().sum().sum()
        )

        duplicates = int(
            df.duplicated().sum()
        )

        preview_df = (
            df.head(10)
            .copy()
        )

        preview_df = preview_df.fillna("")

        preview = (
            preview_df
            .astype(str)
            .to_dict(
                orient="records"
            )
        )

        column_info = []

        for column in df.columns:

            column_info.append({

                "name": str(column),

                "dtype": str(
                    df[column].dtype
                ),

                "missing": int(
                    df[column].isnull().sum()
                ),

                "unique": int(
                    df[column].nunique()
                )

            })

        return jsonify({

            "success": True,

            "filename": filename,

            "rows": rows,

            "columns": columns,

            "missing": missing,

            "duplicates": duplicates,

            "data_type": data_type,

            "column_info": column_info,

            "preview": preview

        })

    except Exception as error:

        print(
            "UPLOAD ERROR:",
            repr(error)
        )

        return jsonify({

            "success": False,

            "error": str(error)

        }), 500


@app.route("/dashboard")
def dashboard():

    return render_template(
        "dashboard.html"
    )


@app.errorhandler(413)
def file_too_large(error):

    return jsonify({

        "success": False,

        "error":
            "File is larger than the 200MB limit."

    }), 413


@app.errorhandler(404)
def not_found(error):

    return jsonify({

        "success": False,

        "error":
            "API route not found."

    }), 404


if __name__ == "__main__":

    print("")
    print("========================================")
    print("       ANOMALY CITY")
    print("========================================")
    print("Server: http://0.0.0.0:5001")
    print("Upload: POST /upload")
    print("Health: GET /health")
    print("Dashboard: GET /dashboard")
    print("========================================")
    print("")

    app.run(
        host="0.0.0.0",
        port=5001,
        debug=False,
        use_reloader=False
    )
