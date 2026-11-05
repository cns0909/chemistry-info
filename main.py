import streamlit as st
import requests
import pandas as pd
from urllib.parse import quote

st.set_page_config(
    page_title="화학 물질 정보 검색",
    page_icon="🧪",
    layout="centered"
)

st.title("🧪 화학 물질 정보 검색")
st.write("물질의 기본 정보와 구조식, 안전 정보를 검색하고 비교할 수 있어요.")


# --------------------------------------------------
# PubChem에서 물질 기본 정보 가져오기
# --------------------------------------------------
@st.cache_data(show_spinner=False)
def get_compound_info(name):
    encoded_name = quote(name)
    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
        f"{encoded_name}/property/MolecularFormula,MolecularWeight/JSON"
    )

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        properties = response.json()["PropertyTable"]["Properties"][0]

        return {
            "CID": properties["CID"],
            "분자식": properties.get("MolecularFormula", "정보 없음"),
            "분자량": properties.get("MolecularWeight", "정보 없음")
        }

    except Exception:
        return None


# --------------------------------------------------
# PubChem 구조 이미지 주소
# --------------------------------------------------
def get_structure_image(cid):
    return (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/"
        f"cid/{cid}/PNG"
    )


# --------------------------------------------------
# PubChem에서 안전 정보 가져오기
# --------------------------------------------------
@st.cache_data(show_spinner=False)
def get_safety_info(cid):
    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/"
        f"{cid}/JSON?heading=Safety%20and%20Hazards"
    )

    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        data = response.json()

        results = []

        def find_text(obj):
            if isinstance(obj, dict):
                information = obj.get("Information")

                if isinstance(information, list):
                    for item in information:
                        value = item.get("Value", {})

                        if isinstance(value, dict):
                            strings = value.get("StringWithMarkup", [])

                            for string_item in strings:
                                text = string_item.get("String")
                                if text:
                                    results.append(text)

                for value in obj.values():
                    find_text(value)

            elif isinstance(obj, list):
                for item in obj:
                    find_text(item)

        find_text(data)

        return list(dict.fromkeys(
            text.strip()
            for text in results
            if isinstance(text, str) and text.strip()
        ))

    except Exception:
        return []


# --------------------------------------------------
# OpenAI API로 안전 정보를 한국어로 요약
# --------------------------------------------------
def summarize_safety_with_ai(chemical_name, safety_info):
    api_key = st.secrets.get("OPENAI_API_KEY", "")

    if not api_key:
        return None, "OPENAI_API_KEY가 설정되지 않았습니다."

    if not safety_info:
        return None, "요약할 안전 정보가 없습니다."

    # 너무 긴 자료가 전송되지 않도록 입력 길이 제한
    source_text = "\n".join(safety_info)[:12000]

    prompt = f"""
다음은 PubChem에서 가져온 화학 물질 안전 정보입니다.

물질 이름: {chemical_name}

안전 정보 원문:
{source_text}

위 원문에 있는 정보만 근거로 한국어 요약을 작성하세요.

다음 항목을 제목과 짧은 문장으로 정리하세요.
1. 물질의 주요 위험성
2. 취급할 때 주의할 점
3. 노출되었을 때 확인할 조치

중요한 규칙:
- 원문에 없는 위험이나 조치를 새로 만들어내지 마세요.
- 원문에 정보가 없는 항목은 "제공된 자료에 정보가 없습니다"라고 표시하세요.
- 위험의 정도를 원문보다 과장하거나 축소하지 마세요.
- 고등학생이 읽기 쉬운 자연스러운 한국어를 사용하세요.
- 안전 정보이므로 핵심 경고와 주의사항을 생략하지 마세요.
- 진단이나 치료 지침을 임의로 추가하지 마세요.
"""

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4.1-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "너는 화학 물질 안전 정보를 정확하고 쉽게 설명하는 도우미야. "
                            "제공된 자료에 없는 내용을 추측하지 마."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.2
            },
            timeout=60
        )

        response.raise_for_status()
        data = response.json()

        summary = data["choices"][0]["message"]["content"]
        return summary, None

    except requests.exceptions.HTTPError:
        return None, (
            "AI 요약 요청에 실패했습니다. API 키, 결제 설정, 사용량 한도를 확인해 주세요."
        )
    except Exception:
        return None, "AI 요약 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."


# --------------------------------------------------
# 세션 상태 초기화
# --------------------------------------------------
if "compare_list" not in st.session_state:
    st.session_state.compare_list = []

if "current_info" not in st.session_state:
    st.session_state.current_info = None


# --------------------------------------------------
# 물질 검색
# --------------------------------------------------
chemical_name = st.text_input(
    "검색할 화학 물질 이름을 입력하세요.",
    placeholder="예: ethanol, caffeine, acetone"
)

if st.button("물질 검색", type="primary"):
    if chemical_name.strip():
        with st.spinner("물질 정보를 검색하고 있어요..."):
            info = get_compound_info(chemical_name.strip())

        if info:
            st.session_state.current_info = info
            st.session_state.current_name = chemical_name.strip()
        else:
            st.session_state.current_info = None
            st.error("물질 정보를 찾지 못했습니다. 영문 이름이나 철자를 확인해 주세요.")


# --------------------------------------------------
# 검색 결과
# --------------------------------------------------
if st.session_state.get("current_info"):
    info = st.session_state.current_info
    name = st.session_state.current_name
    cid = info["CID"]

    st.subheader(f"🔎 {name} 검색 결과")

    col1, col2, col3 = st.columns(3)
    col1.metric("분자식", info["분자식"])
    col2.metric("분자량", f'{info["분자량"]} g/mol')
    col3.metric("PubChem CID", cid)

    # 분자 구조
    st.markdown("### 🧬 분자 구조")

    image_url = get_structure_image(cid)
    st.image(image_url, caption=f"{name}의 분자 구조")

    try:
        image_response = requests.get(image_url, timeout=15)
        image_response.raise_for_status()

        st.download_button(
            label="분자 구조 이미지 다운로드",
            data=image_response.content,
            file_name=f"{name}_structure.png",
            mime="image/png"
        )
    except Exception:
        st.info("분자 구조 이미지를 다운로드하지 못했습니다.")

    # 비교 목록에 추가
    if st.button("비교 목록에 추가"):
        if not any(
            item["CID"] == cid
            for item in st.session_state.compare_list
        ):
            st.session_state.compare_list.append({
                "물질명": name,
                "CID": cid,
                "분자식": info["분자식"],
                "분자량": info["분자량"]
            })
            st.success("비교 목록에 추가했습니다.")
        else:
            st.info("이미 비교 목록에 있는 물질입니다.")

    # 안전 정보
    st.markdown("### ⚠️ 안전 및 유해성 정보")

    with st.spinner("안전 정보를 가져오고 있어요..."):
        safety_info = get_safety_info(cid)

    if safety_info:
        if st.button("🤖 안전 정보 한국어 요약하기"):
            with st.spinner("AI가 안전 정보를 읽기 쉽게 정리하고 있어요..."):
                summary, error = summarize_safety_with_ai(name, safety_info)

            if summary:
                st.session_state.safety_summary = summary
                st.session_state.safety_summary_cid = cid
            else:
                st.session_state.safety_summary = None
                st.warning(error)

        if (
            st.session_state.get("safety_summary")
            and st.session_state.get("safety_summary_cid") == cid
        ):
            st.markdown("#### AI가 정리한 안전 정보")
            st.markdown(st.session_state.safety_summary)

        with st.expander("PubChem 안전 정보 원문 보기"):
            for item in safety_info:
                st.write(f"- {item}")

        st.caption(
            "AI 요약은 참고용이며 원문의 일부 내용이 누락되거나 잘못 정리될 수 있습니다. "
            "실제 취급 전에는 공식 안전자료(SDS)와 원문을 확인하세요."
        )

    else:
        st.info("이 물질의 안전 정보를 가져오지 못했습니다.")


# --------------------------------------------------
# 물질 비교
# --------------------------------------------------
st.divider()
st.subheader("📊 화학 물질 비교")

if st.session_state.compare_list:
    compare_df = pd.DataFrame(st.session_state.compare_list)

    st.dataframe(
        compare_df,
        use_container_width=True,
        hide_index=True
    )

    csv_data = compare_df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        label="비교 결과 CSV 다운로드",
        data=csv_data,
        file_name="chemical_comparison.csv",
        mime="text/csv"
    )

    if st.button("비교 목록 비우기"):
        st.session_state.compare_list = []
        st.rerun()

else:
    st.info("검색한 물질을 비교 목록에 추가하면 여기에 표시됩니다.")


# --------------------------------------------------
# 몰수 계산기
# --------------------------------------------------
st.divider()
st.subheader("🧮 몰수 계산기")

st.write("질량과 분자량을 입력하면 물질의 몰수를 계산할 수 있어요.")

mass = st.number_input(
    "물질의 질량 (g)",
    min_value=0.0,
    value=1.0,
    step=0.1
)

molar_mass = st.number_input(
    "분자량 (g/mol)",
    min_value=0.0,
    value=1.0,
    step=0.1
)

if st.button("몰수 계산"):
    if molar_mass > 0:
        moles = mass / molar_mass
        st.success(f"물질의 몰수는 {moles:.4f} mol 입니다.")
    else:
        st.warning("분자량은 0보다 커야 합니다.")
