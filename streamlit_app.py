import os
import json
import streamlit as st
from dotenv import load_dotenv

from llama_index.core import Settings, get_response_synthesizer
from llama_index.llms.azure_openai import AzureOpenAI

from ingest import build_or_load_index
from decision_schema import Decision

# ---------------------------
# Utilities
# ---------------------------
def _json_from_text(txt: str):
    """Extract valid JSON from a model response.
    - Strips code fences if present
    - Tries to parse first {...} block
    - Falls back to json.loads on whole string
    """
    if not isinstance(txt, str):
        return None
    t = txt.strip()
    # strip ```json ... ``` or ``` ... ```
    if t.startswith("```"):
        # remove all backticks and leading 'json' token if any
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:].strip()
    # try to find the first {...} block
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(t[start:end + 1])
        except Exception:
            pass
    # final attempt
    try:
        return json.loads(t)
    except Exception:
        return None

# ---------------------------
# Streamlit page setup
# ---------------------------
st.set_page_config(page_title="Firstsource SOP Compliance Agent", layout="wide")
load_dotenv()

# ---------------------------
# Sidebar: Configuration
# ---------------------------
st.sidebar.header("Configuration")
az_key = st.sidebar.text_input("AZURE_OPENAI_API_KEY", os.getenv("AZURE_OPENAI_API_KEY", ""), type="password")
az_endpoint = st.sidebar.text_input("AZURE_OPENAI_ENDPOINT", os.getenv("AZURE_OPENAI_ENDPOINT", ""))
az_version = st.sidebar.text_input("AZURE_OPENAI_API_VERSION", os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"))
az_deployment = st.sidebar.text_input("AZURE_OPENAI_DEPLOYMENT_NAME", os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"))
local_emb = st.sidebar.text_input("LOCAL_EMBEDDING_MODEL", os.getenv("LOCAL_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))

# Apply to env so downstream libs see them
if az_key: os.environ["AZURE_OPENAI_API_KEY"] = az_key
if az_endpoint: os.environ["AZURE_OPENAI_ENDPOINT"] = az_endpoint
if az_version: os.environ["AZURE_OPENAI_API_VERSION"] = az_version
if az_deployment: os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"] = az_deployment
if local_emb: os.environ["LOCAL_EMBEDDING_MODEL"] = local_emb

# ---------------------------
# Sidebar: Build / Reload Index
# ---------------------------
st.sidebar.subheader("Index")
if st.sidebar.button("Build / Reload Index"):
    try:
        _ = build_or_load_index(model_name=local_emb)
        st.session_state["index_ready"] = True
        st.success("Index built/loaded.")
    except Exception as e:
        st.error(f"Index error: {e}")
else:
    # Lazy load on first run
    try:
        if "index_ready" not in st.session_state:
            _ = build_or_load_index(model_name=local_emb)
            st.session_state["index_ready"] = True
    except Exception:
        pass

# ---------------------------
# Simple in-session memory
# ---------------------------
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []  # [{role, content}]

# ---------------------------
# Title / Caption
# ---------------------------
st.title("Firstsource SOP Compliance Agent (LlamaIndex + Streamlit)")
st.caption("Doc QA • Retrieve tool • Memory • Decision JSON • Traceability")

# ---------------------------
# Tool: Retrieve Policy (preview chunks)
# ---------------------------
st.subheader("Retrieve Policy (tool)")
q_tool = st.text_input("Retrieval query", value="contractor VPN access duration")
k = st.slider("Top-K", 1, 10, 8)

if st.button("Retrieve Policy"):
    try:
        index = build_or_load_index(model_name=local_emb)
        retriever = index.as_retriever(similarity_top_k=k)
        nodes = retriever.retrieve(q_tool)
        st.success(f"Retrieved {len(nodes)} chunks.")
        for i, n in enumerate(nodes, 1):
            md = n.node.metadata or {}
            page = md.get("page_label", md.get("page", "N/A"))
            score_val = getattr(n, "score", None)
            score_str = f"{score_val:.3f}" if (score_val is not None) else "0"
            st.markdown(f"**{i}. Page {page} — Score: {score_str}**")
            content = n.node.get_content() or ""
            st.write(content[:650] + ("..." if len(content) > 650 else ""))
            fname = md.get("file_name")
            if fname:
                st.caption(f"File: {fname}")
    except Exception as e:
        st.error(f"Retrieve failed: {e}")

st.divider()

# ---------------------------
# Q&A / Decision Mode
# ---------------------------
st.subheader("Ask a Policy Question")
user_q = st.text_input("Your question", value="Can a contractor get VPN access for 90 days?")
decision_mode = st.toggle("Decision Mode (JSON)")

with st.expander("Conversation Memory"):
    if st.session_state["chat_history"]:
        for m in st.session_state["chat_history"]:
            st.write(f"**{m['role']}:** {m['content']}")
    else:
        st.write("_empty_")

# ---------------------------
# LLM init (Azure OpenAI)
# ---------------------------
try:
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")

    llm = AzureOpenAI(
        # some versions accept model=..., others deployment_name=/engine=
        model=deployment,
        deployment_name=deployment,
        engine=deployment,
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        temperature=0.0,
    )

    # Make Azure the default LLM for LlamaIndex (prevents OpenAI fallback)
    Settings.llm = llm

except Exception as e:
    llm = None
    st.error(f"Azure init failed: {e}")

# ---------------------------
# Query function
# ---------------------------
def run_query(q: str, decision: bool):
    index = build_or_load_index(model_name=local_emb)

    # Ensure Azure LLM is used every time
    Settings.llm = llm
    synth = get_response_synthesizer(llm=llm)

    # Build a query engine from the index
    qe = index.as_query_engine(similarity_top_k=k, response_synthesizer=synth)

    if not decision:
        resp = qe.query(q)
        return {"text": str(resp), "nodes": resp.source_nodes}

    # Decision JSON mode (stronger prompt + no code fences)
    schema_hint = '{"verdict":"YES|NO|CONDITIONAL","rationale":"...","citations":["AC-5.1","AC-2.2"]}'
    prompt = (
        "You are a Risk/InfoSec Access Control Compliance Agent.\n"
        "Use ONLY the retrieved SOP context.\n"
        f"Return JSON ONLY (no code fences, no prose) following this schema: {schema_hint}\n"
        "Rules:\n"
        "1) The 'citations' array must include real SOP section IDs present in the retrieved text (e.g., AC-5.1, AC-2.2). Do not invent IDs.\n"
        "2) If the retrieved context lacks enough info, set verdict=CONDITIONAL and state exactly what's missing.\n"
        "3) Keep 'rationale' short (<= 2 sentences).\n"
        f"Question: {q}\n"
    )


    resp = qe.query(prompt)
    txt = str(resp)
    data = _json_from_text(txt)
    if data is None:
        # retry once if JSON malformed
        fix = qe.query(
            f"Return ONLY valid JSON (no code fences) per schema {schema_hint}. "
            f"Fix this: {txt}"
        )
        data = _json_from_text(str(fix)) or {"raw": str(fix)}

    return {"json": data, "nodes": resp.source_nodes}

# ---------------------------
# Run answer
# ---------------------------
if st.button("Answer"):
    if not llm:
        st.error("Azure LLM not configured. Please fill the sidebar credentials.")
    else:
        out = run_query(user_q, decision_mode)
        st.session_state["chat_history"].append({"role": "user", "content": user_q})

        if decision_mode:
            st.subheader("Decision")
            st.code(json.dumps(out.get("json", {}), indent=2), language="json")
            st.session_state["chat_history"].append(
                {"role": "assistant", "content": json.dumps(out.get("json", {}))}
            )
        else:
            st.subheader("Answer")
            st.write(out.get("text", ""))
            st.session_state["chat_history"].append(
                {"role": "assistant", "content": out.get("text", "")}
            )

        # Sources / Traceability
        st.subheader("Sources")
        nodes = out.get("nodes", []) or []
        for i, n in enumerate(nodes, 1):
            md = n.node.metadata or {}
            page = md.get("page_label", md.get("page", "N/A"))
            score_val = getattr(n, "score", None)
            score_str = f"{score_val:.3f}" if (score_val is not None) else "0"
            st.markdown(f"**{i}. Page {page} — Score: {score_str}**")
            content = n.node.get_content() or ""
            st.write(content[:650] + ("..." if len(content) > 650 else ""))
            fname = md.get("file_name")
            if fname:
                st.caption(f"File: {fname}")
