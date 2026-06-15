"""Resume Tailoring Tool — Home page."""
import streamlit as st

st.set_page_config(
    page_title="简历定制工具",
    page_icon="📄",
    layout="wide",
)

# ── Sidebar: API Key status ───────────────────────────────────────────────
from utils.api_key import load_api_key

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

st.sidebar.divider()
st.sidebar.caption("数据存储在本机，不上传云端。")


# ── Main content ───────────────────────────────────────────────────────────

st.title("📄 简历定制工具")
st.caption("一份基础简历 → 适配任意岗位 → 导出 Word 直接投递")

st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("1️⃣ 管理简历")
    st.write("录入你的基础简历。可以存多份——比如「后端开发」「前端开发」各一份。")
    st.write("也支持直接粘贴一段自我描述，无需完整简历。")
    st.page_link("pages/1_Manage_Resumes.py", label="→ 进入管理")

with col2:
    st.subheader("2️⃣ 定制简历")
    st.write("粘贴岗位 JD 或上传截图，AI 自动改写成适配该岗位的简历。")
    st.write("关键词匹配 · 成果重排序 · 绝不编造经历")
    st.page_link("pages/2_Tailor_Resume.py", label="→ 开始定制")

with col3:
    st.subheader("3️⃣ 导出历史")
    st.write("查看过往定制记录，随时重新导出 Word 文件。")
    st.page_link("pages/3_Export_History.py", label="→ 查看历史")

st.divider()

st.info(
    "💡 **使用流程**：先录入基础简历 → 找到心仪岗位 → 粘贴 JD → "
    "一键生成定制版 → 下载 Word 投递。走完一遍不到 2 分钟。"
)
