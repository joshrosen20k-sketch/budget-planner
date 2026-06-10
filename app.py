import json
import math
import os
from datetime import date
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)

SAVE_FILE = os.path.join(os.path.dirname(__file__), "budget_data.json")
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    USE_SUPABASE = True
else:
    USE_SUPABASE = False


def load_data():
    if USE_SUPABASE:
        result = sb.table("budget_data").select("*").eq("id", 1).execute()
        if result.data:
            row = result.data[0]
            return {"goals": row.get("goals") or [], "background": row.get("background")}
        return {"goals": [], "background": None}
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            return json.load(f)
    return {"goals": [], "background": None}


def save_data(data):
    if USE_SUPABASE:
        result = sb.table("budget_data").select("id").eq("id", 1).execute()
        payload = {"goals": data.get("goals", []), "background": data.get("background")}
        if result.data:
            sb.table("budget_data").update(payload).eq("id", 1).execute()
        else:
            sb.table("budget_data").insert({"id": 1, **payload}).execute()
        return
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f)


@app.route("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")


@app.route("/")
def index():
    data = load_data()
    return render_template("index.html", goals=data["goals"], background=data.get("background"))


@app.route("/calculate", methods=["POST"])
def calculate():
    body = request.json
    balance = float(body["balance"])
    monthly_income = float(body["monthly_income"])
    monthly_expenses = float(body["monthly_expenses"])
    spendable = monthly_income - monthly_expenses
    goals = body["goals"]
    today = date.today().isoformat()

    saved_data = load_data()
    saved_goals = {g["name"]: g for g in saved_data.get("goals", [])}

    total_monthly_payments = 0
    results = []

    for goal in goals:
        name = goal["name"]
        cost = float(goal["cost"])
        plan_type = goal.get("plan_type", "save")
        monthly_payment = float(goal.get("monthly_payment") or 0)
        needed = cost - balance

        added_on = goal.get("added_on") or saved_goals.get(name, {}).get("added_on") or today
        goal["added_on"] = added_on

        if needed <= 0:
            results.append({"name": name, "already_have": True, "plan_type": plan_type})
            continue

        if plan_type == "save":
            months_to_save = needed / spendable if spendable > 0 else None

            # Calculate months elapsed since goal was added
            added_date = date.fromisoformat(added_on)
            today_date = date.today()
            months_elapsed = (today_date.year - added_date.year) * 12 + (today_date.month - added_date.month)
            months_remaining = max(0, round(months_to_save - months_elapsed, 1)) if months_to_save else None

            results.append({
                "name": name,
                "already_have": False,
                "plan_type": "save",
                "needed": round(needed, 2),
                "cost": cost,
                "months_to_save": round(months_to_save, 1) if months_to_save else None,
                "months_remaining": months_remaining,
                "months_elapsed": months_elapsed,
                "added_on": added_on,
            })

        else:
            num_payments = math.ceil(needed / monthly_payment) if monthly_payment > 0 else None
            total_paid = monthly_payment * num_payments if num_payments else None
            can_afford = spendable >= monthly_payment
            total_monthly_payments += monthly_payment if can_afford else 0

            results.append({
                "name": name,
                "already_have": False,
                "plan_type": "payment",
                "needed": round(needed, 2),
                "cost": cost,
                "monthly_payment": monthly_payment,
                "num_payments": num_payments,
                "total_paid": round(total_paid, 2) if total_paid else None,
                "can_afford": can_afford,
                "leftover": round(spendable - monthly_payment, 2),
                "shortage": round(monthly_payment - spendable, 2),
            })

    left_after_all = round(spendable - total_monthly_payments, 2)

    saved_data["goals"] = goals
    save_data(saved_data)

    return jsonify({
        "results": results,
        "saved_goals": goals,
        "summary": {
            "spendable": round(spendable, 2),
            "total_monthly_payments": round(total_monthly_payments, 2),
            "left_after_all": left_after_all,
        }
    })


@app.route("/upload-background", methods=["POST"])
def upload_background():
    file = request.files.get("background")
    if not file:
        return jsonify({"error": "No file provided"}), 400

    filename = secure_filename(file.filename)
    file.save(os.path.join(UPLOAD_FOLDER, filename))

    data = load_data()
    data["background"] = f"uploads/{filename}"
    save_data(data)

    return jsonify({"background": f"uploads/{filename}"})


@app.route("/delete-goal", methods=["POST"])
def delete_goal():
    body = request.json
    index = body["index"]
    data = load_data()
    data["goals"].pop(index)
    save_data(data)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=8080, host="0.0.0.0")
