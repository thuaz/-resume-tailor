"""Tailor a resume to a job description — the core workflow."""
import io

import anthropic
import streamlit as st

from config import CLAUDE_MODEL
from db.engine import init_db
from services.claude_client import extract_jd_from_screenshot, tailor_resume_stream
from services.docx_exporter import export_to_docx
from services.resume_service import (
    get_resume,
    list_resumes,
    save_tailored_resume,
)
from utils.api_key import load_api_key

init_db()

st.set_page_config(page_title="定制简历", page_icon="🎯")
st.title("🎯 定制简历")

# ── API Key check ──────────────────────────────────────────────────────────
api_key = load_api_key()
if not api_key:
    st.error("❌ 未配置 API Key。请在项目目录创建 `.env` 文件并写入 `ANTHROPIC_API_KEY=...`")
    st.stop()

client = anthropic.Anthropic(api_key=api_key)

# ── Step 1: Select base resume ─────────────────────────────────────────────

st.subheader("第一步：选择基础简历")
resumes = list_resumes()

use_ad_hoc = False
selected_resume = None

if not resumes:
    st.info("还没有保存的简历。你可以直接在下方的文本框中描述自己，或者先去「管理简历」页面创建一份。")
    use_ad_hoc = True
else:
    tab_select, tab_ad_hoc = st.tabs(["从已保存中选择", "临时输入一段描述"])

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
    ad_hoc_text = st.text_area(
        "输入你的背景描述或简历",
        height=300,
        placeholder="你可以自由描述自己：教育背景、工作/实习经历、项目经历、技能...",
        key="ad_hoc_text",
    )

st.divider()

# ── Step 2: Provide Job Description ────────────────────────────────────────

st.subheader("第二步：输入岗位 JD")
tab_text, tab_image = st.tabs(["📝 粘贴文本", "📸 上传截图"])

jd_text = ""

with tab_text:
    jd_text = st.text_area(
        "岗位描述 (JD)",
        height=250,
        placeholder="把招聘网站上的岗位要求、职责描述粘贴到这里...",
        key="jd_text_paste",
    )

with tab_image:
    uploaded = st.file_uploader(
        "上传 JD 截图（PNG / JPG）",
        type=["png", "jpg", "jpeg"],
        key="jd_screenshot",
    )
    if uploaded is not None:
        st.image(uploaded, caption="上传的截图", use_container_width=True)
        if st.button("🔍 提取文字", type="secondary"):
            with st.spinner("AI 正在识别截图中的文字..."):
                try:
                    extracted = extract_jd_from_screenshot(client, uploaded.getvalue())
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

st.divider()

# ── Step 3: Extra instructions ─────────────────────────────────────────────

st.subheader("第三步：额外指令（可选）")
extra = st.text_input(
    "有什么特殊要求？",
    placeholder="例如: 控制在一页以内 / 突出项目管理经验 / 面向高级职位",
)

st.divider()

# ── Step 4: Generate ───────────────────────────────────────────────────────

st.subheader("第四步：生成定制简历")

# Determine the base resume text
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
    with st.spinner("AI 正在为你定制简历..."):
        try:
            stream = tailor_resume_stream(
                client, base_text, jd_text, extra_instructions=extra
            )
            for chunk in stream:
                full_output += chunk
                output_placeholder.text_area(
                    "定制结果",
                    value=full_output + "▌",
                    height=500,
                    key="streaming_output",
                )
            # Final render without cursor
            output_placeholder.text_area(
                "定制结果",
                value=full_output,
                height=500,
                key="final_output",
            )
        except anthropic.AuthenticationError:
            st.error("API Key 无效，请检查 `.env` 文件中的 ANTHROPIC_API_KEY。")
        except anthropic.RateLimitError:
            st.error("API 调用频率超限，请稍后重试。")
        except Exception as e:
            st.error(f"生成失败: {e}")

    if full_output:
        st.session_state["tailored_output"] = full_output
        st.session_state["tailored_jd"] = jd_text
        st.session_state["tailored_base_id"] = (
            selected_resume.id if selected_resume else None
        )

        # ── Step 5: Save & Export ────────────────────────────────────
        st.divider()
        st.subheader("第五步：保存与导出")

        save_col, export_col, _ = st.columns([1, 1, 2])

        with save_col:
            company = st.text_input("公司名（可选）", key="company_hint", placeholder="如: 字节跳动")
            role = st.text_input("岗位名（可选）", key="role_hint", placeholder="如: 后端开发工程师")
            if st.button("💾 保存到历史", use_container_width=True):
                if st.session_state["tailored_base_id"]:
                    save_tailored_resume(
                        source_resume_id=st.session_state["tailored_base_id"],
                        job_description=jd_text,
                        tailored_text=full_output,
                        company_hint=company,
                        role_hint=role,
                    )
                    st.success("已保存到历史记录 ✅")
                else:
                    st.warning("临时输入的简历不会保存来源关联，但仍可导出 Word。")

        with export_col:
            if st.button("📥 下载 Word (.docx)", type="primary", use_container_width=True):
                try:
                    path = export_to_docx(full_output, company, role)
                    with open(path, "rb") as f:
                        st.download_button(
                            label="📥 点击下载",
                            data=f,
                            file_name=path.name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                        )
                    st.success(f"文件已生成: {path.name}")
                except Exception as e:
                    st.error(f"导出失败: {e}")

        # Also show model info
        st.caption(f"🤖 使用模型: {CLAUDE_MODEL} | 输出长度: {len(full_output)} 字符")
