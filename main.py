
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
st.write("PubChem API를 이용해 화학 물질의 정보를 찾아보세요.")
st.caption("자료 출처: PubChem, National Institutes of Health (NIH)")

st.divider()

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

if "chemical_result" in st.session_state:
    result = st.session_state["chemical_result"]

    st.subheader("📋 검색 결과")

    col1, col2 = st.columns(2)
    col1.metric("분자식", result["분자식"])
    col2.metric("분자량", f'{result["분자량 (g/mol)"]:.3f} g/mol')

    st.write("**검색한 물질:**", result["물질 이름"])
    st.write("**PubChem CID:**", result["CID"])

    image_url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/"
        f'compound/cid/{result["CID"]}/PNG'
    )

    try:
        image_response = requests.get(image_url, timeout=15)
        image_response.raise_for_status()
        st.subheader("🧬 분자 구조")
        st.image(image_response.content, caption="PubChem 분자 구조 이미지")
    except requests.exceptions.RequestException:
        st.info("분자 구조 이미지를 불러오지 못했어요.")

    csv = pd.DataFrame([result]).to_csv(
        index=False
    ).encode("utf-8-sig")

    st.download_button(
        "📥 검색 결과 CSV 다운로드",
        data=csv,
        file_name="chemical_info.csv",
        mime="text/csv",
        use_container_width=True
    )

st.divider()
st.caption("※ 검색 결과는 PubChem에서 제공하는 정보이며, 검색어에 따라 결과가 달라질 수 있습니다.")
