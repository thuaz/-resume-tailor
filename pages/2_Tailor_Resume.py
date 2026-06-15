"""定制简历核心流程 — 选基础简历 → 输入JD → AI生成 → 导出Word。"""
import streamlit as st
from openai import AuthenticationError

from config import DEEPSEEK_MODEL
from db.engine import init_db
from services.claude_client import extract_jd_from_screenshot, tailor_resume_stream
from services.docx_exporter import export_to_docx
from services.resume_service import (
    list_resumes,
    save_tailored_resume,
)
from utils.api_key import load_api_key
from utils.file_parser import extract_text

init_db()

st.set_page_config(page_title="定制简历", page_icon="🎯")
st.title("🎯 定制简历")

# ── API Key 检查 ───────────────────────────────────────────────────────────
api_key = load_api_key()
if not api_key:
    st.error("❌ 未配置 API Key。请在项目目录创建 `.env` 文件并写入 `DEEPSEEK_API_KEY=...`")
    st.stop()

# ── 第一步：选择基础简历 ─────────────────────────────────────────────────

st.subheader("第一步：选择基础简历")
resumes = list_resumes()

use_ad_hoc = False
selected_resume = None

if not resumes:
    st.info("还没有保存的简历。你可以直接在下方文本框中描述自己，或者先上传 Word/PDF 文件，或者去「管理简历」页面创建一份。")
    use_ad_hoc = True
else:
    tab_select, tab_ad_hoc = st.tabs(["从已保存中选择", "临时输入或上传文件"])

    with tab_select:
        resume_names = [r.name for r in resumes]
        chosen = st.selectbox("选择一份基础简历", resume_names, label_visibility="collapsed")
        if chosen:
            selected_resume = next(r for r in resumes if r.name == chosen)
            with st.expander("📄 预览选中的简历"):
                st.text(selected_resume.content[:2000])

    with tab_ad_hoc:
        use_ad_hoc = True

if use_ad_hoc:
    # 支持上传文件自动填充
    uploaded_resume = st.file_uploader(
        "📂 上传简历文件（Word / PDF），自动解析",
        type=["docx", "pdf"],
        key="adhoc_resume_upload",
        help="上传 .docx 或 .pdf 简历文件，自动提取文本填入下方编辑区。",
    )
    if uploaded_resume is not None:
        if st.button("📖 解析上传的简历", type="secondary", key="parse_adhoc"):
            with st.spinner("正在解析简历文件..."):
                try:
                    text = extract_text(uploaded_resume.getvalue(), uploaded_resume.name)
                    st.session_state["adhoc_parsed"] = text
                    st.success(f"✅ 已解析，共 {len(text)} 字")
                except Exception as e:
                    st.error(f"解析失败: {e}")

    default_text = st.session_state.get("adhoc_parsed", "")
    ad_hoc_text = st.text_area(
        "输入你的背景描述或简历",
        value=default_text,
        height=300,
        placeholder="你可以上传 Word/PDF 文件自动填充，或自由描述：教育背景、工作/实习经历、项目经历、技能...",
        key="ad_hoc_text",
    )

st.divider()

# ── 第二步：输入岗位 JD ────────────────────────────────────────────────

st.subheader("第二步：输入岗位 JD")
tab_text, tab_image, tab_file = st.tabs(["📝 粘贴文本", "📸 上传截图", "📄 上传文件"])

jd_text = ""

with tab_text:
    jd_text = st.text_area(
        "岗位描述 (JD)",
        height=250,
        placeholder="把招聘网站上的岗位要求、职责描述粘贴到这里...",
        key="jd_text_paste",
    )

with tab_image:
    uploaded_img = st.file_uploader(
        "上传 JD 截图（PNG / JPG）",
        type=["png", "jpg", "jpeg"],
        key="jd_screenshot",
    )
    if uploaded_img is not None:
        st.image(uploaded_img, caption="上传的截图", use_container_width=True)
        if st.button("🔍 提取文字", type="secondary", key="extract_ocr"):
            with st.spinner("AI 正在识别截图中的文字..."):
                try:
                    extracted = extract_jd_from_screenshot(api_key, uploaded_img.getvalue())
                    st.session_state["extracted_jd"] = extracted
                except Exception as e:
                    st.error(f"提取失败: {e}")

        if "extracted_jd" in st.session_state and st.session_state["extracted_jd"]:
            jd_text = st.text_area(
                "提取结果（可编辑修正）",
                value=st.session_state["extracted_jd"],
                height=300,
                key="jd_text_extracted",
            )

with tab_file:
    uploaded_jd_file = st.file_uploader(
        "上传 JD 文件（Word / PDF）",
        type=["docx", "pdf"],
        key="jd_file_upload",
        help="有些岗位JD是Word或PDF文件，直接上传即可解析。",
    )
    if uploaded_jd_file is not None:
        if st.button("📖 解析 JD 文件", type="secondary", key="parse_jd_file"):
            with st.spinner("正在解析 JD 文件..."):
                try:
                    text = extract_text(uploaded_jd_file.getvalue(), uploaded_jd_file.name)
                    st.session_state["parsed_jd"] = text
                    st.success(f"✅ 已解析，共 {len(text)} 字")
                except Exception as e:
                    st.error(f"解析失败: {e}")

    if "parsed_jd" in st.session_state and st.session_state["parsed_jd"]:
        jd_text = st.text_area(
            "解析结果（可编辑修正）",
            value=st.session_state["parsed_jd"],
            height=300,
            key="jd_text_file",
        )

st.divider()

# ── 第三步：额外指令 ─────────────────────────────────────────────────────

st.subheader("第三步：额外指令（可选）")
extra = st.text_input(
    "有什么特殊要求？",
    placeholder="例如: 控制在一页以内 / 突出项目管理经验 / 面向高级职位 / 强调某项技能",
)

st.divider()

# ── 第四步：生成定制简历 ───────────────────────────────────────────────

st.subheader("第四步：生成定制简历")

# 确定基础简历文本
base_text = ""
if selected_resume and not use_ad_hoc:
    base_text = selected_resume.content
elif use_ad_hoc:
    base_text = ad_hoc_text

can_generate = bool(base_text.strip()) and bool(jd_text.strip())

if not can_generate:
    st.warning("👆 请先完成第一步（基础简历）和第二步（岗位 JD）")

gen_col1, gen_col2 = st.columns([1, 3])
with gen_col1:
    generate_clicked = st.button(
        "🚀 生成定制简历",
        type="primary",
        disabled=not can_generate,
        use_container_width=True,
    )
with gen_col2:
    if not can_generate:
        missing = []
        if not base_text.strip():
            missing.append("基础简历")
        if not jd_text.strip():
            missing.append("岗位JD")
        st.caption(f"还需填写: {', '.join(missing)}")

if generate_clicked:
    output_placeholder = st.empty()

    full_output = ""
    with st.spinner("🤖 AI 正在为你定制简历，请稍候..."):
        try:
            stream = tailor_resume_stream(
                api_key, base_text, jd_text, extra_instructions=extra
            )
            for chunk in stream:
                full_output += chunk
                output_placeholder.text_area(
                    "定制结果（实时输出中）",
                    value=full_output + "▌",
                    height=500,
                    key="streaming_output",
                )
            # 最终渲染（去掉光标）
            output_placeholder.text_area(
                "定制结果",
                value=full_output,
                height=500,
                key="final_output",
            )
        except AuthenticationError:
            st.error("❌ API Key 无效，请检查 `.env` 文件中的 DEEPSEEK_API_KEY 是否正确。")
        except Exception as e:
            st.error(f"❌ 生成失败: {e}")

    if full_output:
        st.session_state["tailored_output"] = full_output
        st.session_state["tailored_jd"] = jd_text
        st.session_state["tailored_base_id"] = (
            selected_resume.id if selected_resume else None
        )

        # ── 第五步：保存与导出 ──────────────────────────────────────────
        st.divider()
        st.subheader("第五步：保存与导出")

        save_col, export_col, _ = st.columns([1, 1, 2])

        with save_col:
            company = st.text_input("公司名称（可选）", key="company_hint", placeholder="如: 字节跳动")
            role = st.text_input("岗位名称（可选）", key="role_hint", placeholder="如: 后端开发工程师")
            if st.button("💾 保存到历史", use_container_width=True):
                if st.session_state["tailored_base_id"]:
                    save_tailored_resume(
                        source_resume_id=st.session_state["tailored_base_id"],
                        job_description=jd_text,
                        tailored_text=full_output,
                        company_hint=company,
                        role_hint=role,
                    )
                    st.success("✅ 已保存到历史记录")
                else:
                    st.warning("⚠️ 临时输入的简历不会关联到已保存的简历，但仍可导出 Word。")

        with export_col:
            if st.button("📥 下载 Word 文件", type="primary", use_container_width=True):
                try:
                    path = export_to_docx(full_output, company, role)
                    with open(path, "rb") as f:
                        st.download_button(
                            label="📥 点击下载 .docx",
                            data=f,
                            file_name=path.name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                        )
                    st.success(f"✅ 文件已生成: {path.name}")
                except Exception as e:
                    st.error(f"❌ 导出失败: {e}")

        # 显示模型信息
        st.caption(f"🤖 使用模型: {DEEPSEEK_MODEL} (DeepSeek) | 输出字数: {len(full_output)} 字符")
