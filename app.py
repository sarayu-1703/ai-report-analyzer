import streamlit as st
import pandas as pd
import fitz
import sqlite3
import hashlib
import os
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq

st.set_page_config(page_title="AI Report Analyzer", layout="wide")

load_dotenv()

# ---------------- GROQ SETUP ----------------

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("GROQ_API_KEY not found. Add it in your .env file.")
    st.stop()

client = Groq(api_key=api_key)

# ---------------- DATABASE ----------------

conn = sqlite3.connect("reports.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    file_name TEXT,
    analysis TEXT,
    created_at TEXT
)
""")

conn.commit()

# ---------------- AUTH FUNCTIONS ----------------

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password):
    try:
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hash_password(password))
        )
        conn.commit()
        return True
    except:
        return False

def login_user(username, password):
    cursor.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username, hash_password(password))
    )
    return cursor.fetchone()

# ---------------- FILE READERS ----------------

def read_pdf(file):
    text = ""
    doc = fitz.open(stream=file.read(), filetype="pdf")

    for page in doc:
        text += page.get_text()

    return text

def read_excel(file):
    text = ""
    excel = pd.ExcelFile(file)

    for sheet in excel.sheet_names:
        df = pd.read_excel(excel, sheet_name=sheet)
        text += f"\n\nSheet Name: {sheet}\n"
        text += df.to_string(index=False)

    return text

# ---------------- AI ANALYSIS ----------------

def ai_analyze(text):
    prompt = f"""
You are a senior business consultant, management analyst, financial analyst, and operations strategist.

Analyze the uploaded report intelligently.

Instructions:
1. Understand the report context before responding.
2. Do NOT use predefined assumptions.
3. Do NOT force sections that are not relevant.
4. If a section is not applicable, omit it.
5. Provide evidence from the report wherever possible.
6. Focus on insights valuable to management.
7. Recommendations should be practical, specific, and prioritized.
8. Create a 30-day action plan ONLY when significant issues, risks, gaps, or opportunities are identified.
9. Avoid generic statements.
10. Do not write phrases like "No action plan required", "Not applicable", or "No problems found".
11. Do not display empty sections.

REPORT CONTENT:
{text[:12000]}

Generate a professional management report using only relevant sections:

# Executive Summary
# Key Findings
# Trends and Patterns Identified
# Risks Identified
# Problems Identified
# Severity Assessment
# Root Cause Analysis
# Business Impact
# Opportunities for Improvement
# Recommendations
# Priority Actions
# 30-Day Action Plan
# Strategic Insights
# Final Conclusion
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    return response.choices[0].message.content

# ---------------- HISTORY FUNCTIONS ----------------

def save_history(username, file_name, analysis):
    cursor.execute(
        """
        INSERT INTO history (username, file_name, analysis, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            username,
            file_name,
            analysis,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    )
    conn.commit()

def get_history(username):
    cursor.execute(
        """
        SELECT id, file_name, analysis, created_at
        FROM history
        WHERE username=?
        ORDER BY id DESC
        """,
        (username,)
    )
    return cursor.fetchall()

# ---------------- SESSION STATE ----------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

# ---------------- LOGIN / REGISTER ----------------

if not st.session_state.logged_in:
    st.title("🔐 AI Report Analyzer")

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login"):
            user = login_user(username, password)

            if user:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Invalid username or password")

    with tab2:
        new_username = st.text_input("Create Username", key="register_username")
        new_password = st.text_input("Create Password", type="password", key="register_password")

        if st.button("Register"):
            if new_username and new_password:
                success = register_user(new_username, new_password)

                if success:
                    st.success("Registration successful. Please login.")
                else:
                    st.error("Username already exists.")
            else:
                st.warning("Please enter username and password.")

# ---------------- MAIN APP ----------------

else:
    st.sidebar.success(f"Logged in as: {st.session_state.username}")

    menu = st.sidebar.radio(
        "Navigation",
        ["Analyze Report", "History", "Logout"]
    )

    if menu == "Logout":
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

    elif menu == "Analyze Report":
        st.title("📊 AI Report Analyzer")
        st.write("Upload a PDF or Excel report. The app will analyze insights, risks, recommendations, and action plan only when required.")

        uploaded_file = st.file_uploader(
            "Upload PDF or Excel Report",
            type=["pdf", "xlsx"]
        )

        if uploaded_file:
            st.success("File Uploaded Successfully")

            if uploaded_file.name.endswith(".pdf"):
                report_text = read_pdf(uploaded_file)
            else:
                report_text = read_excel(uploaded_file)

            st.subheader("📄 Extracted Report Preview")
            st.text_area("Preview", report_text[:5000], height=300)

            if st.button("Analyze Report"):
                with st.spinner("AI is analyzing the report..."):
                    result = ai_analyze(report_text)

                save_history(
                    st.session_state.username,
                    uploaded_file.name,
                    result
                )

                st.subheader("📈 Analysis Results")
                st.markdown(result)

                st.download_button(
                    "Download Analysis",
                    result,
                    file_name="ai_report_analysis.txt",
                    mime="text/plain"
                )

    elif menu == "History":
        st.title("📜 Analysis History")

        history = get_history(st.session_state.username)

        if not history:
            st.info("No analysis history found.")
        else:
            for item in history:
                history_id, file_name, analysis, created_at = item

                with st.expander(f"{file_name} - {created_at}"):
                    st.markdown(analysis)

                    st.download_button(
                        "Download This Analysis",
                        analysis,
                        file_name=f"{file_name}_analysis.txt",
                        mime="text/plain",
                        key=f"download_{history_id}"
                    )