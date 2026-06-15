"""View and re-export past tailored resumes."""
import streamlit as st

from db.engine import init_db
from services.docx_exporter import export_to_docx
from services.resume_service import (
    delete_tailored_resume,
    list_tailored_resumes,
)

init_db()

st.set_page_config(page_title="导出历史", page_icon="📦")
st.title("📦 历史记录")

tailored_list = list_tailored_resumes()

if not tailored_list:
    st.info("还没有定制记录。去「定制简历」页面生成第一份吧。")
    st.stop()

st.caption(f"共 {len(tailored_list)} 条记录")

for tr in tailored_list:
    source_name = tr.source_resume.name if tr.source_resume else "(已删除)"
    label_parts = [source_name]
    if tr.company_hint:
        label_parts.append(f"→ {tr.company_hint}")
    if tr.role_hint:
        label_parts.append(f"| {tr.role_hint}")
    label_parts.append(f"| {tr.created_at.strftime('%Y-%m-%d %H:%M')}")

    with st.expander("  ".join(label_parts)):
        # Preview
        st.text_area(
            "定制简历预览",
            value=tr.tailored_text[:3000],
            height=300,
            key=f"preview_{tr.id}",
            disabled=True,
        )
        st.caption(f"JD 原文: {tr.job_description[:200]}...")

        c1, c2 = st.columns([1, 3])
        with c1:
            if st.button("📥 下载 Word", key=f"export_{tr.id}"):
                path = export_to_docx(tr.tailored_text, tr.company_hint, tr.role_hint)
                with open(path, "rb") as f:
                    st.download_button(
                        label="点击下载",
                        data=f,
                        file_name=path.name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
        with c2:
            if st.button("🗑 删除记录", key=f"del_hist_{tr.id}"):
                delete_tailored_resume(tr.id)
                st.rerun()
