# 🌊 simple-injection-mold GUI (개인 테스트용)

**개인의 수치해석 학습 및 사출성형 유동 해석 테스트를 위한 간이 GUI 대시보드**

본 프로젝트는 Windows 환경에서 **BlueCFD-Core (OpenFOAM 호환)** 기반의 오픈소스 해석 엔진을 호출하여, 개인적으로 사출성형 유동 해석을 공부하고 테스트해보기 위해 구축한 Streamlit 기반의 간단한 GUI 프로토타입 대시보드입니다.

⚠️ **필독 고지 및 면책 조항 (Disclaimer)**
- **본 프로젝트는 상용 사출성형 설계, 양산 제품 검증 또는 학술 연구 목적으로 적합하지 않으며, 이를 보증하지 않습니다.**
- 순수하게 개인의 학습, 수치해석 공부 및 간단한 기능 테스트를 위한 목적으로만 개발된 **미완성 단계의 개인 실험용 도구**입니다.
- **현재 GUI 및 UI 구성이 완벽하지 않으며, 일부 기능이 정상적으로 동작하지 않는 현상이 있어 이를 해결하고 개선하기 위한 구현 방안을 깊이 고민하고 있는 상태입니다.**
- 본 프로젝트는 개발 생산성 향상 및 학습을 위해 AI 코딩 어시스턴트(AI Coding Assistant)의 기술적 조력과 코드 생성을 활용하여 구축되었습니다.

---

## 🛠️ 주요 기능 및 모듈 구성 (개인 실험용)

1. **간이 전처리 (Pre-process)**: 개인 테스트용 CAD STL 파일 업로드 및 가상의 사출기 사양 설정.
2. **격자 설정 (Mesh)**: `blockMesh` 및 `snappyHexMesh`를 활용한 공부용 격자망 설정 테스트.
3. **간이 재료 설정 (Material)**: 테스트용 간이 재료 정보를 조회 및 매핑하는 기능.
4. **공정 조건 설정 (Process)**: 보압 시간/압력 제어 및 온도 프로파일 설정을 공부하기 위한 간이 제어 기능.
5. **구조 연계 테스트 (Structural)**: 사출해석 데이터를 기반으로 피로수명이나 다성분 균질화(Halpin-Tsai) 개념을 테스트해보기 위한 실험적 연계 기능.
6. **품질 검토 (Quality)**: 제품 변형(Warpage) 리스크 및 웰드라인(Weld-line) 발생 경향을 개인적으로 관찰해보기 위한 경향성 검토 기능.
7. **자가 검증 (V&V)**: 테스트 해석이 정상적으로 수렴하는지 기초적인 벤치마크 데이터를 통해 자가 진단하는 기능.
8. **간이 솔버 제어 (Expert)**: OpenFOAM 솔버의 이완 계수 등을 변경하며 수치해석 거동 변화를 공부하는 세팅.
9. **시각화 및 리포트 (Post-process)**: 개인적인 테스트 결과를 HTML 및 PPTX 형태로 간이 출력 및 가시화해보기 위한 출력 기능.

---

## 🏗️ 기술 스택

- **프론트엔드 GUI**: Streamlit
- **웹 게이트웨이**: Python FastAPI, Celery
- **수치해석 엔진**: OpenFOAM 12 (BlueCFD-Core 2024-1)
- **테스트 프레임워크**: Pytest

---

## 🚀 시작하기 (개인 로컬 환경)

### 사전 요구사항
- Windows OS (7/10/11)
- BlueCFD-Core가 시스템 환경 변수(PATH)에 설정되어 있어야 합니다.
- Python 3.10 이상

### 설치 및 실행

1. **저장소 복제**
   ```powershell
   git clone https://github.com/hwangsk83/injection_mold_.git
   cd injection_mold_
   ```

2. **가상환경 설정 및 의존성 설치**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. **실행 방법**
   로컬에서 Streamlit 서버를 기동합니다:
   ```powershell
   streamlit run app.py
   ```
   브라우저에서 `http://localhost:8501`로 접속하여 테스트합니다.

---

## ⚖️ 라이센스 및 법적 고지

### 오픈소스 솔버 출처 및 크레딧 (Credits)
- 본 프로젝트의 수치해석 솔버 코드([solvers/](file:///D:/Open_code_project/injection_mold_/solvers))는 OpenFOAM 기반의 오픈소스 사출성형 해석 프로젝트인 **[openInjMoldSim](https://github.com/krebeljk/openInjMoldSim)**의 물리 모델링 기법(Cross-WLF 비뉴턴 유체 점도 모델 및 Modified Tait PVT 상태방정식)을 참고하여 구현되었습니다. 원작자분들의 기여에 깊이 감사드립니다.

### 라이센스 (License)
- 본 프로젝트 및 기반 솔버는 **GPLv3 (GNU General Public License v3)** 라이센스를 따릅니다. 본 도구에 포함된 모든 C++ 솔버 코드 역시 동일한 라이센스 조건 하에 소스코드가 공개 배포됩니다.
- 본 소프트웨어는 blueCFD-Core®의 바이너리 파일들을 자체적으로 내장하고 있지 않으며, 사용자의 PC 환경에 설치된 blueCFD-Core 환경 변수를 통해 간접적으로 명령어(subprocess)를 호출하여 작동합니다.

### 상표권 귀속 고지 (Trademark Attribution)
- **blueCFD-Core®** 및 **blueCFD®**는 **blueCAPE Lda.**의 등록상표입니다. 본 프로젝트 및 개발자는 blueCAPE Lda.와 아무런 공식 제휴, 후원 또는 보증 관계가 없으며, 본 프로젝트는 개인의 학습 및 테스트를 위해 작성된 순수 래퍼(Wrapper) 대시보드임을 명시합니다.
- 본 프로젝트는 Autodesk, Inc.의 등록상표인 `Moldflow`와 일절 무관하며, 어떠한 상용 상표권 침해 의도 없이 개발되었습니다.
