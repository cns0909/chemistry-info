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
        data = response.json()

        properties = data["PropertyTable"]["Properties"][0]

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
# 안전 정보 표현을 읽기 쉬운 한국어로 정리
# --------------------------------------------------
def translate_safety_terms(text):
    replacements = {
        "Safety and Hazards": "안전 및 유해성",
        "Hazard Statements": "유해·위험 문구",
        "Precautionary Statements": "예방조치 문구",
        "First Aid Measures": "응급조치",
        "Fire Fighting Measures": "화재 진압 방법",
        "Accidental Release Measures": "누출 사고 시 조치",
        "Handling and Storage": "취급 및 저장 방법",
        "Exposure Controls and Personal Protection": "노출 방지 및 개인 보호구",
        "Toxicity": "독성",
        "Health Hazard": "건강 유해성",
        "Environmental Hazard": "환경 유해성",
        "Danger": "위험",
        "Warning": "경고",
        "Causes serious eye irritation": "심한 눈 자극을 일으킬 수 있습니다.",
        "Causes skin irritation": "피부 자극을 일으킬 수 있습니다.",
        "May cause respiratory irritation": "호흡기 자극을 일으킬 수 있습니다.",
        "Harmful if swallowed": "삼키면 유해할 수 있습니다.",
        "Avoid breathing dust": "분진을 흡입하지 않도록 주의해야 합니다.",
        "Wear protective gloves": "보호장갑을 착용해야 합니다.",
        "Keep out of reach of children": "어린이의 손이 닿지 않는 곳에 보관해야 합니다.",
        "May cause": "일으킬 수 있습니다.",
        "Causes": "일으킵니다.",
        "Do not": "하지 마세요.",
        "Avoid": "피해야 합니다."
    }

    result = text

    for english, korean in replacements.items():
        result = result.replace(english, korean)

    return result


# --------------------------------------------------
# 안전 정보를 항목별로 분류
# --------------------------------------------------
def organize_safety_info(safety_info):
    categories = {
        "위험성": [],
        "취급 시 주의사항": [],
        "기타 안전 정보": []
    }

    hazard_keywords = [
        "hazard", "toxic", "toxicity", "irritation", "harmful",
        "danger", "warning", "carcinogenic", "flammable"
    ]

    precaution_keywords = [
        "avoid", "wear", "keep", "store", "handling",
        "protective", "do not", "first aid"
    ]

    for item in safety_info:
        lower_item = item.lower()

        if any(word in lower_item for word in hazard_keywords):
            categories["위험성"].append(item)
        elif any(word in lower_item for word in precaution_keywords):
            categories["취급 시 주의사항"].append(item)
        else:
            categories["기타 안전 정보"].append(item)

    return categories


# --------------------------------------------------
# 세션 상태 초기화
# --------------------------------------------------
if "compare_list" not in st.session_state:
    st.session_state.compare_list = []


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
        organized_info = organize_safety_info(safety_info)

        for category, items in organized_info.items():
            if items:
                st.markdown(f"#### {category}")

                for item in items:
                    korean_text = translate_safety_terms(item)

                    st.markdown(f"- {korean_text}")

        with st.expander("영어 원문 보기"):
            for item in safety_info:
                st.write(f"- {item}")

        st.caption(
            "한국어 설명은 주요 안전 용어를 바꿔 표시한 것입니다. "
            "모든 문장이 완전히 번역된 것은 아니므로, 실제 취급 전에는 "
            "공식 안전자료(SDS)와 원문을 확인하세요."
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
