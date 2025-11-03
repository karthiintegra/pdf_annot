import streamlit as st
import tempfile
import os
from pdfixsdk import *
from work1 import PdfTagTransformerPhase1, Reference, Table, footprint  # adjust import as per your actual filename

# Initialize Pdfix
pdfix = GetPdfix()
if not pdfix:
    st.error("❌ Failed to initialize Pdfix")
    st.stop()


# Helper to save uploaded file temporarily
def save_uploaded_file(uploaded_file):
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, uploaded_file.name)
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return temp_path


# Title
st.title("📄 PDF Tag Transformer App (Phases 1–4)")

# File uploader
uploaded_pdf = st.file_uploader("Upload a PDF to process", type=["pdf"])

if uploaded_pdf:
    input_pdf_path = save_uploaded_file(uploaded_pdf)
    st.success(f"✅ Uploaded: {uploaded_pdf.name}")

    # Phase selection
    st.header("⚙️ Choose processing phases to apply")
    phase1 = st.checkbox("Phase 1 (Steps 1–13)")
    phase2 = st.checkbox("Phase 2 – Reference (Steps 14–17)")
    phase3 = st.checkbox("Phase 3 – Table (Steps 18–24)")
    phase4 = st.checkbox("Phase 4 – Footprint (Steps 25–30)")

    if st.button("🚀 Run Selected Phases"):
        # Log container
        progress_log = st.empty()
        output_pdf_path = input_pdf_path

        # Run selected phases
        if phase1:
            phase1_output = output_pdf_path.replace(".pdf", "_phase1.pdf")
            st.write("📘 Running Phase 1...")
            transformer = PdfTagTransformerPhase1(pdfix)
            transformer.modify_pdf_tags(output_pdf_path, phase1_output)
            output_pdf_path = phase1_output
            progress_log.write("✅ Phase 1 complete")

        if phase2:
            phase2_output = output_pdf_path.replace(".pdf", "_phase2.pdf")
            st.write("📘 Running Phase 2...")
            reference = Reference(pdfix)
            reference.modify_pdf_tags(output_pdf_path, phase2_output)
            output_pdf_path = phase2_output
            progress_log.write("✅ Phase 2 complete")

        if phase3:
            phase3_output = output_pdf_path.replace(".pdf", "_phase3.pdf")
            st.write("📘 Running Phase 3...")
            table = Table(pdfix)
            table.modify_pdf_tags(output_pdf_path, phase3_output)
            output_pdf_path = phase3_output
            progress_log.write("✅ Phase 3 complete")

        if phase4:
            phase4_output = output_pdf_path.replace(".pdf", "_phase4.pdf")
            st.write("📘 Running Phase 4...")
            fp = footprint(pdfix)
            fp.modify_pdf_tags(output_pdf_path, phase4_output)
            output_pdf_path = phase4_output
            progress_log.write("✅ Phase 4 complete")

        # Final output
        st.success("🎉 All selected phases complete!")
        with open(output_pdf_path, "rb") as f:
            st.download_button(
                label="⬇️ Download Processed PDF",
                data=f,
                file_name=os.path.basename(output_pdf_path),
                mime="application/pdf",
            )

