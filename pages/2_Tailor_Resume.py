"""定制简历 — 详细信息流（高级用户和从首页跳转过来的人用）。"""
import streamlit as st
from openai import AuthenticationError

from config import DEEPSEEK_MODEL
from db.engine import init_db
from services.claude_client import extract_jd_from_screenshot, tailor_resume_stream
from services.docx_exporter import export_to_docx
from services.resume_service import list_resumes, save_tailored_resume
from utils.api_key import load_api_key
from utils.file_parser import extract_text
from utils.jd_fetcher import fetch_jd_from_url

init_db()

st.set_page_config(page_title="定制简历", page_icon="🎯")
st.title("🎯 定制简历")

# ── API Key 检查 ───────────────────────────────────────────────────────────
api_key = load_api_key()
if not api_key:
    st.error("❌ 未配置 API Key。请在项目目录创建 `.env` 文件并写入 `DEEPSEEK_API_KEY=...`")
    st.stop()

# ── 第一步：基础简历 ──────────────────────────────────────────────────────

st.subheader("第一步：基础简历")
resumes = list_resumes()

use_ad_hoc = False
selected_resume = None
base_text = ""

if not resumes:
    st.info("还没有保存的简历。上传文件或者直接写几行描述，或者去「管理简历」创建。")
    use_ad_hoc = True
else:
    tab_select, tab_ad_hoc = st.tabs(["从已保存中选择", "临时输入或上传文件"])

    with tab_select:
        last_used = st.session_state.get("last_resume_id")
        last_idx = 0
        if last_used:
            for i, r in enumerate(resumes):
                if r.id == last_used:
                    last_idx = i
                    break
        resume_names = [r.name for r in resumes]
        chosen = st.selectbox("选择一份", resume_names, index=last_idx)
        if chosen:
            selected_resume = next(r for r in resumes if r.name == chosen)
            base_text = selected_resume.content
            with st.expander("👀 预览"):
                st.text(base_text[:2000])

    with tab_ad_hoc:
        use_ad_hoc = True

if use_ad_hoc:
    uploaded = st.file_uploader(
        "📂 上传简历文件（Word / PDF），或直接在下方面描述",
        type=["docx", "pdf"],
        key="adtail_upload",
    )
    if uploaded and st.button("📖 解析上传的简历", key="adtail_parse"):
        with st.spinner("解析中..."):
            try:
                base_text = extract_text(uploaded.getvalue(), uploaded.name)
                st.success(f"✅ 共 {len(base_text)} 字")
            except Exception as e:
                st.error(f"失败: {e}")

    ad_hoc_text = st.text_area(
        "简历内容（可直接写，也可等上传解析自动填入）",
        value=base_text,
        height=300,
        placeholder="随便写几行描述自己，AI 能理解。也可以上传 Word/PDF 文件自动填入。",
        key="adtail_text",
    )
    base_text = ad_hoc_text

st.divider()

# ── 第二步：岗位 JD ────────────────────────────────────────────────────────

st.subheader("第二步：岗位 JD")
tab_link, tab_text, tab_image, tab_file = st.tabs(
    ["🔗 粘贴链接", "📝 粘贴文字", "📸 上传截图", "📄 上传文件"]
)

jd_text = ""

with tab_link:
    jd_url = st.text_input("招聘页面网址", placeholder="https://...", key="adtail_url")
    if jd_url and st.button("🌐 抓取", key="adtail_fetch"):
        with st.spinner("抓取中..."):
            try:
                jd_text = fetch_jd_from_url(jd_url)
                st.success(f"✅ {len(jd_text)} 字")
            except Exception as e:
                st.error(f"❌ {e}")
    if jd_text:
        jd_text = st.text_area("抓取结果（可修改）", value=jd_text, height=250, key="adtail_url_result")

with tab_text:
    jd_text = st.text_area(
        "岗位描述", height=250, placeholder="粘贴招聘要求...", key="adtail_paste"
    )

with tab_image:
    uploaded_img = st.file_uploader("截图", type=["png", "jpg", "jpeg"], key="adtail_img")
    if uploaded_img:
        st.image(uploaded_img, width=400)
        if st.button("🔍 识别", key="adtail_ocr"):
            with st.spinner("识别中..."):
                try:
                    jd_text = extract_jd_from_screenshot(api_key, uploaded_img.getvalue())
                    st.success("✅")
                except Exception as e:
                    st.error(f"{e}")
        if jd_text:
            jd_text = st.text_area("识别结果", value=jd_text, height=250, key="adtail_ocr_result")

with tab_file:
    uploaded_jd = st.file_uploader("JD 文件", type=["docx", "pdf"], key="adtail_jdfile")
    if uploaded_jd and st.button("📖 解析", key="adtail_jdparse"):
        with st.spinner("解析中..."):
            try:
                jd_text = extract_text(uploaded_jd.getvalue(), uploaded_jd.name)
                st.success(f"✅ {len(jd_text)} 字")
            except Exception as e:
                st.error(f"{e}")
    if jd_text:
        jd_text = st.text_area("解析结果", value=jd_text, height=250, key="adtail_jdresult")

st.divider()

# ── 第三步：额外要求 ──────────────────────────────────────────────────────

st.subheader("第三步：额外要求（可选）")
extra = st.text_input("特殊要求？", placeholder="例如: 一页以内 / 突出项目经历", key="adtail_extra")

st.divider()

# ── 第四步：生成 ──────────────────────────────────────────────────────────

st.subheader("第四步：生成")
can_generate = bool(base_text.strip()) and bool(jd_text.strip())
if not can_generate:
    st.warning("👆 还差基础简历和岗位 JD")

gen_col1, gen_col2 = st.columns([1, 3])
with gen_col1:
    generate_clicked = st.button(
        "🚀 生成定制简历", type="primary", disabled=not can_generate, use_container_width=True
    )
with gen_col2:
    if not can_generate:
        st.caption(f"还差: {'基础简历' if not base_text.strip() else ''} {' / ' if not base_text.strip() and not jd_text.strip() else ''} {'岗位JD' if not jd_text.strip() else ''}")

if generate_clicked:
    placeholder = st.empty()
    full_output = ""
    with st.spinner("🤖 正在定制..."):
        try:
            for chunk in tailor_resume_stream(api_key, base_text, jd_text, extra):
                full_output += chunk
                placeholder.text_area("生成中", value=full_output + "▌", height=400, key="adtail_stream")
            placeholder.text_area("生成中", value=full_output, height=400, key="adtail_final", label_visibility="collapsed")
        except AuthenticationError:
            st.error("❌ API Key 无效")
            st.stop()
        except Exception as e:
            st.error(f"❌ {e}")
            st.stop()

    # 格式化预览
    st.divider()
    st.subheader("📋 预览")
    prev_col, act_col = st.columns([3, 1])
    with prev_col:
        with st.container(border=True):
            st.markdown(full_output)
    with act_col:
        auto_company = ""
        for line in jd_text.split("\n")[:5]:
            line = line.strip()
            if any(kw in line for kw in ["公司", "有限", "科技", "技术"]):
                auto_company = line[:30]
                break
        company = st.text_input("公司", value=auto_company, placeholder="如: 字节", key="adtail_company")
        role = st.text_input("岗位", placeholder="如: 后端", key="adtail_role")

        if st.button("💾 保存", use_container_width=True, key="adtail_save"):
            try:
                if selected_resume:
                    rid = selected_resume.id
                else:
                    from services.resume_service import create_resume
                    r = create_resume(role or company or "定制", base_text, "")
                    rid = r.id
                save_tailored_resume(rid, jd_text, full_output, company, role)
                st.success("✅ 已保存")
            except Exception as e:
                st.warning(f"{e}")

        st.divider()
        if st.button("📥 下载 Word", type="primary", use_container_width=True, key="adtail_dl"):
            try:
                path = export_to_docx(full_output, company, role)
                with open(path, "rb") as f:
                    st.download_button(
                        "点击下载", f, file_name=path.name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                    )
                st.success(f"✅ {path.name}")
            except Exception as e:
                st.error(f"{e}")

        if selected_resume:
            st.session_state["last_resume_id"] = selected_resume.id

    st.caption(f"🤖 {DEEPSEEK_MODEL} | {len(full_output)} 字")
