"""简历定制工具 — 首页 + 快速开始（无需跳页面，一个地方搞定）。"""
import streamlit as st
from openai import AuthenticationError

from config import DEEPSEEK_MODEL
from db.engine import init_db
from services.claude_client import (
    extract_jd_from_screenshot,
    generate_resume_stream,
    tailor_resume_stream,
)
from services.docx_exporter import export_to_docx
from services.resume_service import (
    create_resume,
    get_resume,
    list_resumes,
    save_tailored_resume,
)
from utils.api_key import load_api_key
from utils.file_parser import extract_text
from utils.jd_fetcher import fetch_jd_from_url

init_db()

st.set_page_config(
    page_title="简历定制工具",
    page_icon="📄",
    layout="wide",
)

# ── Sidebar: API Key + 快捷入口 ────────────────────────────────────────────

api_key = load_api_key()

st.sidebar.title("⚙️ 设置")
if api_key:
    st.sidebar.success("✅ DeepSeek API Key 已配置")
else:
    st.sidebar.error("❌ 未找到 API Key")
    st.sidebar.info(
        "在项目目录创建 `.env` 文件并写入：\n\n"
        "```\nDEEPSEEK_API_KEY=sk-...\n```\n\n"
        "获取 Key: https://platform.deepseek.com/api_keys"
    )
    st.stop()

st.sidebar.divider()
st.sidebar.subheader("📂 高级功能")
st.sidebar.page_link("pages/1_Manage_Resumes.py", label="→ 管理已保存的简历")
st.sidebar.page_link("pages/3_Export_History.py", label="→ 查看历史定制记录")
st.sidebar.divider()
st.sidebar.caption("💾 数据存储在本机，不上传云端。")

# ── 顶部标题 ────────────────────────────────────────────────────────────────

st.title("📄 简历定制工具")
st.caption("不用打字太多，几下就搞定一份适配岗位的简历，直接下载投递。")

# ── 第一步：简历来源 ─────────────────────────────────────────────────────

st.subheader("① 我的简历 / 背景")

source_col1, source_col2 = st.columns(2)

with source_col1:
    source_mode = st.radio(
        "简历来源",
        options=["📝 简单描述自己（最省事）", "📂 从已保存中选择", "📤 上传简历文件"],
        label_visibility="collapsed",
        horizontal=False,
    )

base_text = ""
selected_resume = None

if "📝 简单描述" in source_mode:
    desc = st.text_area(
        "随便写几句，AI 帮你整理成正式简历",
        height=150,
        placeholder="""不用写得很正式，随便描述就行：

我叫张三，XX大学计算机系2024年毕业。
在ABC公司实习了6个月，做后端开发，主要用Python和Django。
自己做过一个在线商城的项目，用了Vue和Spring Boot。
英语还行，过了六级。""",
        help="越随意越好，想到什么写什么。AI 会帮你整理成专业格式。",
        key="quick_desc",
    )

elif "已保存" in source_mode:
    resumes = list_resumes()
    if resumes:
        # 默认选上次使用的简历
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
            with st.expander("👀 点开预览"):
                st.text(base_text[:1500])
    else:
        st.info("还没有保存的简历。建议选「简单描述自己」，更快。")

else:  # 上传文件
    uploaded_resume = st.file_uploader(
        "拖入或点击上传 Word / PDF 简历",
        type=["docx", "pdf"],
        key="home_resume_upload",
    )
    if uploaded_resume:
        if st.button("📖 解析文件", key="parse_home"):
            with st.spinner("正在解析..."):
                try:
                    base_text = extract_text(uploaded_resume.getvalue(), uploaded_resume.name)
                    st.success(f"✅ 已解析，共 {len(base_text)} 字")
                except Exception as e:
                    st.error(f"解析失败: {e}")
        if base_text:
            with st.expander("👀 点开预览解析结果"):
                st.text(base_text[:1500])

st.divider()

# ── 第二步：岗位 JD ─────────────────────────────────────────────────────

st.subheader("② 岗位 JD（招聘要求）")

jd_mode = st.radio(
    "JD 输入方式",
    options=["🔗 粘贴链接（最省事）", "📝 粘贴文字", "📸 上传截图", "📄 上传文件"],
    horizontal=True,
    label_visibility="collapsed",
)

jd_text = ""

if "链接" in jd_mode:
    jd_url = st.text_input(
        "把招聘页面的网址粘贴到这里",
        placeholder="例如: https://www.zhipin.com/job_detail/xxx.html",
        key="jd_url",
    )
    if jd_url and st.button("🌐 抓取 JD 内容", type="secondary"):
        with st.spinner("正在从网页抓取 JD..."):
            try:
                jd_text = fetch_jd_from_url(jd_url)
                st.success(f"✅ 已抓取，共 {len(jd_text)} 字")
            except Exception as e:
                st.error(f"❌ {e}")
    if jd_text:
        jd_text = st.text_area(
            "抓取结果（可直接编辑修正）",
            value=jd_text,
            height=250,
            key="jd_url_result",
        )

elif "文字" in jd_mode:
    jd_text = st.text_area(
        "把招聘要求粘贴在这里",
        height=200,
        placeholder="把岗位职责、任职要求粘贴到这里...",
        key="jd_paste",
    )

elif "截图" in jd_mode:
    uploaded_img = st.file_uploader(
        "上传 JD 截图（PNG / JPG）",
        type=["png", "jpg", "jpeg"],
        key="home_jd_img",
    )
    if uploaded_img:
        st.image(uploaded_img, caption="预览", width=400)
        if st.button("🔍 AI 识别截图文字", type="secondary"):
            with st.spinner("正在识别..."):
                try:
                    jd_text = extract_jd_from_screenshot(api_key, uploaded_img.getvalue())
                    st.success(f"✅ 识别完成")
                except Exception as e:
                    st.error(f"识别失败: {e}")
        if jd_text:
            jd_text = st.text_area("识别结果（可修改）", value=jd_text, height=250, key="jd_ocr_result")

else:  # 上传文件
    uploaded_jd = st.file_uploader(
        "上传 JD 文件（Word / PDF）",
        type=["docx", "pdf"],
        key="home_jd_file",
    )
    if uploaded_jd and st.button("📖 解析 JD 文件", key="parse_home_jd"):
        with st.spinner("正在解析..."):
            try:
                jd_text = extract_text(uploaded_jd.getvalue(), uploaded_jd.name)
                st.success(f"✅ 已解析，共 {len(jd_text)} 字")
            except Exception as e:
                st.error(f"解析失败: {e}")
    if jd_text:
        jd_text = st.text_area("解析结果（可修改）", value=jd_text, height=250, key="jd_file_result")

st.divider()

# ── 第三步：额外要求（可选）─────────────────────────────────────────────

st.subheader("③ 额外要求（可选，不填也行）")
extra = st.text_input(
    "有什么特殊要求？",
    placeholder="例如: 控制在一页以内 / 突出项目经验 / 用词专业一些",
    key="home_extra",
)

st.divider()

# ── 第四步：生成 ────────────────────────────────────────────────────────

st.subheader("④ 生成")

# 确定基础文本
if not base_text and "简单描述" in source_mode:
    base_text = desc

can_generate = bool(base_text.strip()) and bool(jd_text.strip())

gen_col1, gen_col2 = st.columns([1, 3])
with gen_col1:
    generate_clicked = st.button(
        "🚀 一键生成定制简历",
        type="primary",
        disabled=not can_generate,
        use_container_width=True,
    )
with gen_col2:
    if not can_generate:
        missing = []
        if not base_text.strip():
            missing.append("简历/背景描述")
        if not jd_text.strip():
            missing.append("岗位JD")
        st.caption(f"👆 还差: {', '.join(missing)}")

# ── 生成逻辑 ─────────────────────────────────────────────────────────────

if generate_clicked:
    st.divider()

    # 如果是简单描述，先让 AI 生成正式简历
    if "简单描述" in source_mode:
        st.info("📝 第一步：把描述整理成正式简历...")
        formal_placeholder = st.empty()
        formal_text = ""
        try:
            for chunk in generate_resume_stream(api_key, base_text):
                formal_text += chunk
                formal_placeholder.text_area(
                    "AI 生成的正式简历",
                    value=formal_text + "▌",
                    height=300,
                    key="formal_stream",
                )
            formal_placeholder.text_area(
                "AI 生成的正式简历",
                value=formal_text,
                height=300,
                key="formal_final",
            )
            base_text = formal_text
            st.success("✅ 正式简历已生成，接下来根据 JD 定制...")
        except Exception as e:
            st.error(f"生成正式简历失败: {e}")
            st.stop()

    # 第二步：根据 JD 定制
    with st.spinner("🤖 正在根据 JD 定制你的简历..."):
        output_placeholder = st.empty()
        full_output = ""
        try:
            stream = tailor_resume_stream(api_key, base_text, jd_text, extra)
            for chunk in stream:
                full_output += chunk
                output_placeholder.text_area(
                    "正在生成...",
                    value=full_output + "▌",
                    height=400,
                    key="tailor_stream",
                )
            output_placeholder.text_area(
                "正在生成...",
                value=full_output,
                height=400,
                key="tailor_final",
                label_visibility="collapsed",
            )
        except AuthenticationError:
            st.error("❌ API Key 无效，请检查 `.env` 文件。")
            st.stop()
        except Exception as e:
            st.error(f"❌ 生成失败: {e}")
            st.stop()

    # ── 格式化预览 ─────────────────────────────────────────────────────
    st.subheader("📋 预览与下载")

    preview_col, action_col = st.columns([3, 1])

    with preview_col:
        # 用 markdown 渲染，把 ## 变成 markdown 标题
        preview_text = full_output
        # 转为 markdown 展示
        with st.container(border=True):
            st.markdown(preview_text)

    with action_col:
        st.caption("💾 保存到我的简历库")
        # 自动提取公司名和岗位名
        auto_company = ""
        auto_role = ""
        # 尝试从JD文本提取公司名（简单启发式）
        for line in jd_text.split("\n")[:5]:
            line = line.strip()
            if "公司" in line or "有限" in line or "科技" in line:
                auto_company = line[:30]
                break

        company = st.text_input("公司", value=auto_company, placeholder="如: 字节跳动", key="home_company")
        role = st.text_input("岗位", value=auto_role, placeholder="如: 后端开发", key="home_role")

        if st.button("💾 保存", use_container_width=True):
            try:
                # 先保存基础简历（如果是描述生成的）
                if selected_resume:
                    rid = selected_resume.id
                else:
                    name = role or company or "快速定制"
                    r = create_resume(f"{name}_{len(base_text)}字", base_text, "快速生成")
                    rid = r.id
                    st.session_state["last_resume_id"] = rid
                    st.success(f"✅ 简历「{r.name}」已保存")

                save_tailored_resume(rid, jd_text, full_output, company, role)
                st.success("✅ 已保存到历史")
            except Exception as e:
                st.warning(f"保存失败（不影响下载）: {e}")

        st.divider()
        if st.button("📥 下载 Word", type="primary", use_container_width=True):
            try:
                path = export_to_docx(full_output, company, role)
                with open(path, "rb") as f:
                    st.download_button(
                        label="📥 点击下载 .docx 文件",
                        data=f,
                        file_name=path.name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                    )
                st.success(f"✅ 已生成: {path.name}")
            except Exception as e:
                st.error(f"导出失败: {e}")

        # 记住这次选中的简历
        if selected_resume:
            st.session_state["last_resume_id"] = selected_resume.id

    st.caption(f"🤖 模型: {DEEPSEEK_MODEL} | 输出 {len(full_output)} 字")
