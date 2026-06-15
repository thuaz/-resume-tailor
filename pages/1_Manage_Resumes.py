"""管理基础简历 — 创建、编辑、删除，支持上传 Word/PDF 自动解析。"""
import streamlit as st

from db.engine import init_db
from services.resume_service import (
    create_resume,
    delete_resume,
    get_resume,
    list_resumes,
    update_resume,
)
from utils.file_parser import extract_text

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
        st.info("还没有简历，在右侧上传文件或手动输入创建第一份吧。")

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

    # 检查是否有预选的简历
    if "edit_id" in st.query_params:
        try:
            selected_id = int(st.query_params["edit_id"])
        except (ValueError, TypeError):
            pass

with right:
    editing_resume = get_resume(selected_id) if selected_id else None

    if editing_resume:
        st.subheader(f"✏️ 编辑: {editing_resume.name}")
    else:
        st.subheader("➕ 新建简历")

    # ── 文件上传（仅新建模式下显示，上传后自动填入内容）───
    auto_content = None
    auto_name = None

    if not editing_resume:
        uploaded_file = st.file_uploader(
            "📂 上传简历文件（Word / PDF），自动解析文本",
            type=["docx", "pdf"],
            key="resume_file_upload",
            help="支持 .docx 和 .pdf 格式，上传后自动提取文本填入下方编辑区。",
        )
        if uploaded_file is not None and "last_uploaded" not in st.session_state:
            st.session_state["last_uploaded"] = uploaded_file.name
            st.session_state["parsed_content"] = None

        if uploaded_file is not None:
            if (
                "parsed_content" not in st.session_state
                or st.session_state["parsed_content"] is None
                or st.session_state.get("last_uploaded") != uploaded_file.name
            ):
                with st.spinner("📖 正在解析简历文件..."):
                    try:
                        text = extract_text(uploaded_file.getvalue(), uploaded_file.name)
                        st.session_state["parsed_content"] = text
                        st.session_state["last_uploaded"] = uploaded_file.name
                        st.success(f"✅ 已解析「{uploaded_file.name}」，共 {len(text)} 字")
                    except Exception as e:
                        st.error(f"❌ 解析失败: {e}")
                        st.session_state["parsed_content"] = None

            if st.session_state.get("parsed_content"):
                auto_content = st.session_state["parsed_content"]
                # 用文件名（去掉扩展名）作为默认简历名称
                auto_name = uploaded_file.name.rsplit(".", 1)[0]

    with st.form("resume_form", clear_on_submit=not editing_resume):
        name = st.text_input(
            "简历名称",
            value=editing_resume.name if editing_resume else (auto_name or ""),
            placeholder="例如: 后端开发工程师、前端开发工程师",
            help="给这份简历起个名字，方便区分。",
        )
        content = st.text_area(
            "简历内容",
            value=editing_resume.content if editing_resume else (auto_content or ""),
            height=400,
            placeholder="""可以上传 Word/PDF 文件自动填充，或直接粘贴简历全文，也可以用自然语言描述自己。

例如：
我叫张三，2024年毕业于XX大学计算机科学专业。
实习经历：在ABC公司做了6个月后端开发实习生...
技能：Python, Java, Docker, MySQL...
项目经历：做了一个在线商城系统...
""",
            help="可以粘贴完整简历，也可以自由描述——AI 都能处理。也支持上传 Word/PDF 文件自动解析。",
        )
        notes = st.text_input(
            "备注（可选）",
            value=editing_resume.notes if editing_resume else "",
            placeholder="例如: 通用版本、侧重后端方向",
        )

        submitted = st.form_submit_button(
            "💾 保存修改" if editing_resume else "💾 创建简历",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            if not name.strip():
                st.error("请输入简历名称。")
            elif not content.strip():
                st.error("请输入简历内容，或上传 Word/PDF 文件。")
            else:
                if editing_resume:
                    update_resume(editing_resume.id, name, content, notes)
                    st.success(f"✅ 已更新「{name}」")
                else:
                    create_resume(name, content, notes)
                    # 清除上传缓存
                    st.session_state.pop("parsed_content", None)
                    st.session_state.pop("last_uploaded", None)
                    st.success(f"✅ 已创建「{name}」")
                st.rerun()
