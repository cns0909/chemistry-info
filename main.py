import streamlit as st
import requests
import pandas as pd
from urllib.parse import quote

st.set_page_config(
    page_title="화학 물질 정보 검색",
    page_icon="🧪",
    layout="wide"
)

st.title("🧪 화학 물질 정보 검색")
st.write("PubChem API를 이용해 화학 물질의 정보와 분자 구조를 확인해 보세요.")
st.caption("자료 출처: PubChem, National Institutes of Health (NIH)")

st.divider()


# -----------------------------
# PubChem 검색 함수
# -----------------------------
@st.cache_data(ttl=3600)
def search_chemical(name):
    safe_name = quote(name.strip(), safe="")

    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/"
        f"compound/name/{safe_name}/property/"
        "MolecularFormula,MolecularWeight/JSON"
    )

    response = requests.get(url, timeout=15)

    if response.status_code == 404:
        return None

    response.raise_for_status()
    data = response.json()
    properties = data["PropertyTable"]["Properties"][0]

    return {
        "물질 이름": name.strip(),
        "분자식": properties["MolecularFormula"],
        "분자량 (g/mol)": float(properties["MolecularWeight"]),
        "CID": properties["CID"]
    }


@st.cache_data(ttl=3600)
def get_structure_image(cid):
    """PubChem에서 2D 분자 구조 이미지 가져오기"""
    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/"
        f"compound/cid/{cid}/PNG"
    )

    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response.content


@st.cache_data(ttl=3600)
def get_safety_info(cid):
    """PubChem PUG View에서 안전성·위험성 관련 자료 가져오기"""
    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/"
        f"data/compound/{cid}/JSON"
    )

    response = requests.get(
        url,
        params={"heading": "Safety and Hazards"},
        timeout=20
    )

    if response.status_code == 404:
        return []

    response.raise_for_status()
    data = response.json()

    rows = []

    def extract_text(value):
        """PubChem 자료에서 표시할 문자열 추출"""
        texts = []

        if isinstance(value, dict):
            if isinstance(value.get("String"), str):
                texts.append(value["String"])

            for key, item in value.items():
                if key == "String":
                    continue
                texts.extend(extract_text(item))

        elif isinstance(value, list):
            for item in value:
                texts.extend(extract_text(item))

        return texts

    def read_sections(sections, parent_heading=""):
        for section in sections or []:
            heading = section.get("TOCHeading", parent_heading)

            for info in section.get("Information", []):
                name = info.get("Name", "항목")
                value_texts = extract_text(info.get("Value", []))

                value_texts = list(dict.fromkeys(
                    text.strip()
                    for text in value_texts
                    if text.strip()
                ))

                if value_texts:
                    rows.append({
                        "구분": heading,
                        "항목": name,
                        "내용": " / ".join(value_texts)
                    })

            read_sections(section.get("Section", []), heading)

    record = data.get("Record", {})
    read_sections(record.get("Section", []))

    return rows


# -----------------------------
# 검색 영역
# -----------------------------
chemical_name = st.text_input(
    "검색할 화학 물질 이름",
    placeholder="예: water, glucose, caffeine"
)

if st.button("🔍 물질 검색", type="primary", use_container_width=True):
    if not chemical_name.strip():
        st.warning("화학 물질 이름을 입력해 주세요.")
    else:
        try:
            result = search_chemical(chemical_name)

            if result is None:
                st.error("해당 물질을 찾지 못했어요. 영문 이름을 확인해 주세요.")
            else:
                st.session_state["chemical_result"] = result

        except requests.exceptions.Timeout:
            st.error("응답 시간이 초과되었어요. 잠시 후 다시 시도해 주세요.")
        except requests.exceptions.RequestException:
            st.error("인터넷 연결이나 PubChem 서버를 확인해 주세요.")
        except (KeyError, IndexError, ValueError):
            st.error("자료를 읽는 중 오류가 발생했어요. 다른 이름으로 검색해 보세요.")


# -----------------------------
# 검색 결과
# -----------------------------
if "chemical_result" in st.session_state:
    result = st.session_state["chemical_result"]
    cid = result["CID"]

    st.subheader("📋 검색 결과")

    col1, col2 = st.columns(2)
    col1.metric("분자식", result["분자식"])
    col2.metric(
        "분자량",
        f'{result["분자량 (g/mol)"]:.3f} g/mol'
    )

    st.write("**검색한 물질:**", result["물질 이름"])
    st.write("**PubChem CID:**", cid)

    st.markdown(
        f"[🔗 PubChem에서 자세히 보기]"
        f"(https://pubchem.ncbi.nlm.nih.gov/compound/{cid})"
    )

    # -----------------------------
    # 분자 구조
    # -----------------------------
    st.divider()
    st.subheader("🧬 분자 구조")

    try:
        structure_image = get_structure_image(cid)

        st.image(
            structure_image,
            caption="PubChem 2D 분자 구조 이미지",
            width=450
        )

        st.download_button(
            "📥 분자 구조 이미지 PNG 다운로드",
            data=structure_image,
            file_name=f"chemical_structure_{cid}.png",
            mime="image/png",
            use_container_width=True
        )

        st.caption(
            "분자 구조 이미지는 원자와 결합이 어떻게 연결되어 있는지 보여주는 "
            "2D 표현입니다."
        )

    except requests.exceptions.RequestException:
        st.info(
            "분자 구조 이미지를 불러오지 못했어요. "
            "PubChem 페이지에서 확인해 주세요."
        )

    # -----------------------------
    # 안전성 및 위험성 정보
    # -----------------------------
    st.divider()
    st.subheader("🛡️ 안전성 및 위험성 정보")

    try:
        safety_rows = get_safety_info(cid)

        if safety_rows:
            safety_df = pd.DataFrame(safety_rows)

            st.dataframe(
                safety_df,
                use_container_width=True,
                hide_index=True
            )

            st.caption(
                "자료는 PubChem에 수록된 주석 정보입니다. "
                "항목별 의미와 적용 조건은 원문 출처에서 확인해 주세요."
            )

            st.markdown(
                f"[PubChem 안전성 자료 원문 보기]"
                f"(https://pubchem.ncbi.nlm.nih.gov/compound/{cid}#section=Safety-and-Hazards)"
            )

        else:
            st.info(
                "PubChem에서 이 물질의 안전성 관련 자료를 찾지 못했어요. "
                "자료가 없다는 뜻이지, 안전하다는 뜻은 아닙니다."
            )

    except requests.exceptions.Timeout:
        st.warning("안전성 자료를 불러오는 데 시간이 오래 걸렸어요.")
    except requests.exceptions.RequestException:
        st.warning(
            "안전성 자료를 불러오지 못했어요. "
            "잠시 후 다시 시도해 주세요."
        )
    except (KeyError, TypeError, ValueError):
        st.warning("안전성 자료의 형식을 읽지 못했어요.")

    # -----------------------------
    # 물질 비교 목록에 추가
    # -----------------------------
    st.divider()
    st.subheader("📊 물질 비교")

    if "comparison_list" not in st.session_state:
        st.session_state["comparison_list"] = []

    if st.button("➕ 이 물질을 비교 목록에 추가"):
        existing_cids = [
            item["CID"] for item in st.session_state["comparison_list"]
        ]

        if cid not in existing_cids:
            st.session_state["comparison_list"].append(result)
            st.success("비교 목록에 추가했어요.")
        else:
            st.info("이미 비교 목록에 있는 물질이에요.")


# -----------------------------
# 비교 목록
# -----------------------------
if "comparison_list" not in st.session_state:
    st.session_state["comparison_list"] = []

if st.session_state["comparison_list"]:
    comparison_df = pd.DataFrame(st.session_state["comparison_list"])

    st.dataframe(
        comparison_df,
        use_container_width=True,
        hide_index=True
    )

    csv_comparison = comparison_df.to_csv(
        index=False
    ).encode("utf-8-sig")

    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            "📥 비교 목록 CSV 다운로드",
            data=csv_comparison,
            file_name="chemical_comparison.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col2:
        if st.button("🗑️ 비교 목록 비우기", use_container_width=True):
            st.session_state["comparison_list"] = []
            st.rerun()


# -----------------------------
# 몰수 및 질량 계산기
# -----------------------------
st.divider()
st.subheader("🧮 몰수·질량 계산기")
st.write("분자량을 이용해 물질의 질량과 몰수 사이를 변환할 수 있어요.")

if "chemical_result" in st.session_state:
    default_molar_mass = st.session_state["chemical_result"]["분자량 (g/mol)"]
else:
    default_molar_mass = 18.015

molar_mass = st.number_input(
    "분자량 또는 몰 질량 (g/mol)",
    min_value=0.000001,
    value=float(default_molar_mass),
    format="%.6f"
)

calc_mode = st.radio(
    "계산할 값",
    ["질량(g) → 몰수(mol)", "몰수(mol) → 질량(g)"],
    horizontal=True
)

if calc_mode == "질량(g) → 몰수(mol)":
    mass = st.number_input(
        "질량 (g)",
        min_value=0.0,
        value=1.0,
        step=0.1
    )

    if st.button("몰수 계산", use_container_width=True):
        amount = mass / molar_mass
        st.success(f"몰수: **{amount:.6f} mol**")

else:
    amount = st.number_input(
        "몰수 (mol)",
        min_value=0.0,
        value=1.0,
        step=0.1
    )

    if st.button("질량 계산", use_container_width=True):
        mass = amount * molar_mass
        st.success(f"질량: **{mass:.6f} g**")


st.divider()
st.caption(
    "※ 검색 결과는 PubChem에서 제공하는 정보이며, "
    "검색어에 따라 결과가 달라질 수 있습니다."
)
