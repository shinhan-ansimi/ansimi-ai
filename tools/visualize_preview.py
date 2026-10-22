"""1.4(수집)·2.1(정제·격자) 결과를 발표용 이미지로 저장.

실행:
    cd ansimi-ai
    python3 tools/visualize_preview.py
    -> docs/collection_map.png (1.4), docs/grid_preview.png (2.1) 생성

주의: 여기서 그리는 건 1.4/2.1 산출물 검증·발표용이지, 2.2(v1 규칙 가중치 위험도)의
공식 위험 스코어가 아니다.
"""
from __future__ import annotations

import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd

KOREAN_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/AppleSDGothicNeo.ttc",  # macOS
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",  # macOS (older)
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux
]


def _set_korean_font() -> None:
    for path in KOREAN_FONT_CANDIDATES:
        if os.path.exists(path):
            fm.fontManager.addfont(path)
            plt.rcParams["font.family"] = fm.FontProperties(fname=path).get_name()
            plt.rcParams["axes.unicode_minus"] = False
            return


def plot_collection_map(clean_facilities_csv: str, out_path: str) -> None:
    """1.4: 정제된(bbox 밖/중복 제거 완료) 포인트를 카테고리별로 지도에 찍는다 — 실데이터 카테고리만."""
    labels = {
        "cctv": ("CCTV (전국표준데이터)", "#1f77b4"),
        "route_cctv": ("안심귀갓길 CCTV", "#17becf"),
        "route_emergency_bell": ("안심귀갓길 안심벨", "#d62728"),
        "route_security_light": ("안심귀갓길 보안등", "#ff7f0e"),
        "route_signage": ("안심귀갓길 표지판", "#9467bd"),
    }

    df = pd.read_csv(clean_facilities_csv, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(10, 11))
    for cat, (label, color) in labels.items():
        sub = df[df["category"] == cat]
        if sub.empty:
            continue
        ax.scatter(sub["lon"], sub["lat"], s=3, alpha=0.5, color=color, label=f"{label} ({len(sub):,}건)")

    ax.set_title("1.4 위험 데이터 조사·수집 — 실데이터 수집 현황 (서울 전역)", fontsize=15, pad=14)
    ax.set_xlabel("경도")
    ax.set_ylabel("위도")
    ax.set_aspect("equal")
    ax.legend(markerscale=4, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2, fontsize=10)

    plt.tight_layout()
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    plt.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"saved -> {out_path}")


def plot_grid_result(grid_csv: str, out_path: str) -> None:
    """2.1: 정제·격자 생성 결과 — 안전시설 밀도, 위험요인 배분, 공식 안심귀갓길 통과 격자."""
    df = pd.read_csv(grid_csv, encoding="utf-8-sig")
    facility_cols = [c for c in df.columns if c.endswith("_count")]
    df["facility_total"] = df[facility_cols].sum(axis=1)

    fig, axes = plt.subplots(1, 3, figsize=(21, 7))

    sc0 = axes[0].scatter(
        df["center_lon"], df["center_lat"], c=df["facility_total"], s=2, cmap="YlOrRd",
        vmax=df["facility_total"].quantile(0.98),
    )
    axes[0].set_title(f"격자별 안전시설 총량\n(안전시설 {len(facility_cols)}종 합계)", fontsize=11)
    axes[0].set_xlabel("경도")
    axes[0].set_ylabel("위도")
    fig.colorbar(sc0, ax=axes[0], shrink=0.8, label="시설 개수")

    combo = df["low_night_population_risk"].fillna(0) * 0.5 + df["crime_rate_risk"].fillna(0) * 0.5
    sc1 = axes[1].scatter(df["center_lon"], df["center_lat"], c=combo, s=2, cmap="Blues")
    axes[1].set_title("자치구 단위 위험요인 격자 배분\n(심야 유동인구 희소 + 범죄율, 단순 평균)", fontsize=11)
    axes[1].set_xlabel("경도")
    axes[1].set_ylabel("위도")
    fig.colorbar(sc1, ax=axes[1], shrink=0.8, label="위험가중치(0~1)")

    axes[2].scatter(df["center_lon"], df["center_lat"], s=1, color="#dddddd")
    on_route = df[df.get("on_safe_route", 0) == 1]
    axes[2].scatter(on_route["center_lon"], on_route["center_lat"], s=4, color="crimson")
    axes[2].set_title(f"공식 안심귀갓길(OA-21695) 통과 격자\n({len(on_route):,}개 셀, 실데이터 362개 경로 기준)", fontsize=11)
    axes[2].set_xlabel("경도")
    axes[2].set_ylabel("위도")

    fig.suptitle(f"2.1 정제·격자 생성 — 100m×100m 격자 {len(df):,}개", fontsize=15)
    plt.tight_layout(rect=(0, 0, 1, 0.93))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    plt.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"saved -> {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean-facilities-csv", default="data_pipeline/output/clean/facilities_clean.csv")
    parser.add_argument("--grid-csv", default="data_pipeline/output/grid/risk_grid.csv")
    parser.add_argument("--collection-out", default="docs/collection_map.png")
    parser.add_argument("--grid-out", default="docs/grid_preview.png")
    args = parser.parse_args()

    _set_korean_font()
    plot_collection_map(args.clean_facilities_csv, args.collection_out)
    plot_grid_result(args.grid_csv, args.grid_out)


if __name__ == "__main__":
    main()
