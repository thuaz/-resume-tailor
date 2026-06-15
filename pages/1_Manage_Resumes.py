"""Manage base resumes — create, edit, delete."""
import streamlit as st

from db.engine import init_db
from services.resume_service import (
    create_resume,
    delete_resume,
    get_resume,
    list_resumes,
    update_resume,
)

# ── Init ───────────────────────────────────────────────────────────────────
init_db()

st.set_page_config(page_title="管理简历", page_icon="📋")
st.title("📋 管理基础简历")

# ── Layout: left (list) / right (editor) ──────────────────────────────────

left, right = st.columns([1, 2])

with left:
    st.subheader("我的简历")
    resumes = list_resumes()

    if not resumes:
        st.info("还没有简历，在右侧创建第一份吧。")

    selected_id = None
    for r in resumes:
        col_btn, col_label = st.columns([0.3, 0.7])
        with col_label:
            if st.button(r.name, key=f"select_{r.id}", use_container_width=True):
                selected_id = r.id
                st.rerun()
        with col_btn:
            if st.button("🗑", key=f"del_{r.id}", help=f"删除 {r.name}"):
                delete_resume(r.id)
                st.rerun()

    # Check query params for pre-selected resume
    if "edit_id" in st.query_params:
        try:
            selected_id = int(st.query_params["edit_id"])
        except (ValueError, TypeError):
            pass

with right:
    # Determine mode: create new or edit existing
    editing_resume = get_resume(selected_id) if selected_id else None

    if editing_resume:
        st.subheader(f"✏️ 编辑: {editing_resume.name}")
    else:
        st.subheader("➕ 新建简历")

    with st.form("resume_form", clear_on_submit=not editing_resume):
        name = st.text_input(
            "简历名称",
            value=editing_resume.name if editing_resume else "",
            placeholder="例如: 后端开发工程师、前端开发工程师",
            help="给这份简历起个名字，方便区分。",
        )
        content = st.text_area(
            "简历内容",
            value=editing_resume.content if editing_resume else "",
            height=400,
            placeholder="""粘贴你的简历全文，或者用自然语言描述自己。例如：

我叫张三，2024年毕业于XX大学计算机科学专业。
实习经历：在ABC公司做了6个月后端开发实习生...
技能：Python, Java, Docker, MySQL...
项目：做了一个在线商城系统...
""",
            help="可以粘贴完整简历，也可以自由描述——AI 都能处理。",
        )
        notes = st.text_input(
            "备注（可选）",
            value=editing_resume.notes if editing_resume else "",
            placeholder="例如: 通用版本、侧重后端",
        )

        submitted = st.form_submit_button(
            "💾 保存" if editing_resume else "💾 创建",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            if not name.strip():
                st.error("请输入简历名称。")
            elif not content.strip():
                st.error("请输入简历内容。")
            else:
                if editing_resume:
                    update_resume(editing_resume.id, name, content, notes)
                    st.success(f"✅ 已更新「{name}」")
                else:
                    create_resume(name, content, notes)
                    st.success(f"✅ 已创建「{name}」")
                st.rerun()
