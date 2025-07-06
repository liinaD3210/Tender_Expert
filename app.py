# app.py

import streamlit as st
import pandas as pd
import numpy as np
import os
import io
from document_parser import get_text_from_file
from llm_handler import (
    extract_data_from_text, 
    normalize_and_group_items, 
    generate_tender_insight,
    generate_search_query,
    analyze_search_results
)
from internet_search import google_search

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def load_file_bytes(filepath):
    try:
        with open(filepath, "rb") as f: return f.read()
    except FileNotFoundError: return None

def to_excel(df: pd.DataFrame):
    output = io.BytesIO()
    df_for_excel = df.fillna('')
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_for_excel.to_excel(writer, index=False, sheet_name='Сравнение')
    return output.getvalue()

# --- UI Настройка ---
st.set_page_config(layout="wide", page_title="Тендер-Эксперт")
st.title("AI-анализатор Тендер-Эксперт")
st.write("Интеллектуальный помощник для анализа коммерческих предложений и поиска лучших цен на рынке.")

# --- Инициализация состояния сессии ---
if 'demo_mode' not in st.session_state:
    st.session_state.demo_mode = False
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None

# --- Создание вкладок ---
tab1, tab2 = st.tabs(["📁 Сравнение предложений", "🌐 Поиск по рынку"])

# --- Логика для первой вкладки ---
with tab1:
    st.header("Шаг 1: Выберите источник файлов")
    DEMO_FILES_DIR = "demo_files"
    try:
        demo_filenames = sorted([f for f in os.listdir(DEMO_FILES_DIR) if os.path.isfile(os.path.join(DEMO_FILES_DIR, f))])
    except FileNotFoundError: demo_filenames = []

    if demo_filenames:
        with st.container(border=True):
            st.subheader("✨ Нет своих файлов под рукой?")
            st.write("Попробуйте наш демонстрационный набор коммерческих предложений:")
            if st.button("Использовать демо-файлы", type="primary"):
                st.session_state.demo_mode = True
                st.session_state.uploader_key = (st.session_state.get('uploader_key', 0) + 1)
                st.session_state.analysis_results = None # Сбрасываем старые результаты
                st.rerun()
            
            st.markdown("Или скачайте их, чтобы посмотреть:"); cols = st.columns(len(demo_filenames))
            for i, filename in enumerate(demo_filenames):
                with cols[i]:
                    file_path = os.path.join(DEMO_FILES_DIR, filename)
                    file_bytes = load_file_bytes(file_path)
                    if file_bytes:
                        st.download_button(label=f"📄 {filename}", data=file_bytes, file_name=filename)
    st.markdown("---")
    
    st.subheader("Или загрузите свои файлы:")
    uploaded_files = st.file_uploader(
        "Нажмите, чтобы выбрать файлы, или перетащите их сюда", # Это и есть новый label
        accept_multiple_files=True,
        type=['pdf', 'xlsx', 'docx'],
        # label_visibility="collapsed" <- УБИРАЕМ или меняем на "visible"
        key=f"uploader_{st.session_state.get('uploader_key', 0)}"
    )
    if uploaded_files:
        st.session_state.demo_mode = False
        st.session_state.analysis_results = None # Сбрасываем старые результаты

    files_to_process = []
    if st.session_state.demo_mode:
        for filename in demo_filenames:
            file_path = os.path.join(DEMO_FILES_DIR, filename)
            file_bytes = load_file_bytes(file_path)
            if file_bytes: files_to_process.append({"name": filename, "data": file_bytes})
    elif uploaded_files:
        for uploaded_file in uploaded_files:
            files_to_process.append({"name": uploaded_file.name, "data": uploaded_file.getvalue()})

    if st.session_state.demo_mode: st.success("Выбран демо-режим. Нажмите 'Сравнить предложения', чтобы начать.")

    st.header("Шаг 2: Запустите анализ")
    if st.button("Сравнить предложения", disabled=not files_to_process, key="compare_button"):
        with st.spinner("Выполняю полный анализ..."):
            all_items = []
            with st.status("Анализ документов...", expanded=True) as status:
                for file_info in files_to_process:
                    filename, file_data = file_info["name"], file_info["data"]
                    st.write(f"Обработка файла: {filename}...")
                    text = get_text_from_file(io.BytesIO(file_data), filename)
                    supplier_name = filename.split('.')[0]
                    extracted_items = extract_data_from_text(text, supplier_name)
                    if extracted_items: all_items.extend(extracted_items)
                    else: st.warning(f"Не удалось извлечь структурированные данные из файла: {filename}")
                status.update(label="✅ Документы проанализированы!", state="complete")

            if all_items:
                normalized_data = normalize_and_group_items(all_items)
                if normalized_data:
                    suppliers = sorted(list(set(item['supplier'] for item in all_items)))
                    table_data = []
                    for group in normalized_data:
                        row = {"Номенклатура": group['canonical_name']}
                        offers_by_supplier = {offer['supplier']: offer.get('price_per_unit') for offer in group['offers']}
                        for supplier in suppliers:
                            price = offers_by_supplier.get(supplier)
                            row[supplier] = float(price) if price is not None else np.nan
                        table_data.append(row)
                    df = pd.DataFrame(table_data)
                    insight_text = generate_tender_insight(df.to_json(orient='records', force_ascii=False), {s: df[s].sum() for s in suppliers})
                    
                    # Сохраняем ВСЕ результаты в сессию
                    st.session_state.analysis_results = {
                        "df": df,
                        "insight_text": insight_text,
                        "suppliers": suppliers
                    }
                else: st.error("Не удалось сгруппировать позиции.")
            else: st.error("Не удалось извлечь данные ни из одного файла.")
    
    # --- БЛОК ОТОБРАЖЕНИЯ РЕЗУЛЬТАТОВ (работает всегда, если есть данные в сессии) ---
    if st.session_state.analysis_results:
        st.success("🎉 Анализ завершен! Результаты представлены ниже:")
        
        df = st.session_state.analysis_results["df"]
        insight_text = st.session_state.analysis_results["insight_text"]
        suppliers = st.session_state.analysis_results["suppliers"]
        
        def highlight_min_universal(s):
            if s.count() == 0: return ['' for _ in s]
            min_val = s.min()
            return ['border: 2px solid #3c78e4; font-weight: bold;' if v == min_val else '' for v in s]
        
        styled_df = df.style.apply(highlight_min_universal, axis=1, subset=suppliers).format({s: "{:,.2f}" for s in suppliers}, na_rep="—")
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        excel_data = to_excel(df)
        st.download_button(label="📥 Скачать отчет в формате Excel", data=excel_data, file_name="tender_expert_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        st.markdown("---")
        st.subheader("Итоговые суммы по поставщикам")
        totals = {"Номенклатура": "**ИТОГО**"}
        for s in suppliers:
            totals[s] = f"**{df[s].sum():,.2f} ₽**" if df[s].sum() > 0 else "—"
        cols = st.columns(len(df.columns))
        for i, col_name in enumerate(df.columns):
            with cols[i]:
                st.markdown(f"**{col_name}**"); st.markdown(totals.get(col_name, ''))
        
        st.markdown("---")
        st.info(f"**Инсайт от AI-агента:**\n\n{insight_text}")

# --- Логика для второй вкладки ---
with tab2:
    # ... код для второй вкладки остается без изменений ...
    st.header("Найдите лучшее предложение в интернете")
    item_to_search = st.text_input("Введите наименование товара:", placeholder="Например, Подшипник 6205-2RS")
    if st.button("🔍 Найти предложения", disabled=not item_to_search, key="search_button"):
        with st.spinner("Формирую поисковый запрос..."):
            search_query = generate_search_query(item_to_search)
            st.write(f"Ищем по запросу: *«{search_query}»*")
        with st.spinner("Выполняю поиск в интернете..."):
            search_results = google_search(search_query)
        if not search_results:
            st.error("Не удалось найти информацию по вашему запросу.")
        else:
            with st.spinner("Анализирую найденные предложения..."):
                offers = analyze_search_results(search_results, item_to_search)
            if not offers:
                st.warning("Поиск дал результаты, но AI-агент не смог извлечь из них конкретные ценовые предложения.")
            else:
                prices = [o['price'] for o in offers if 'price' in o and o['price'] is not None and o['price'] > 0]
                if prices:
                    st.metric(label="Средняя цена на рынке (по найденным предложениям)", value=f"~ {sum(prices) / len(prices):,.2f} ₽")
                else:
                    st.info("Не удалось найти достаточно данных для расчета средней цены.")
                with st.expander(f"Показать найденные предложения ({len(offers)} шт.)"):
                    sorted_offers = sorted(offers, key=lambda x: x.get('price', float('inf')))
                    for offer in sorted_offers:
                        with st.container(border=True):
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.subheader(offer.get('supplier_name', 'Неизвестный поставщик'))
                                st.markdown(f"*{offer.get('snippet', 'Нет описания...')}*")
                                st.markdown(f"[Перейти на страницу]({offer.get('link')})", unsafe_allow_html=True)
                            with col2:
                                price = offer.get('price')
                                if price:
                                    st.metric(label="Цена", value=f"{price:,.2f} ₽")
                                else:
                                    st.metric(label="Цена", value="Не найдена")

# --- Плашка-дисклеймер в футере ---
st.divider()
st.caption("Proof of Concept (v0.1). Это демонстрационная версия, подтверждающая основную концепцию. Проект открыт для дальнейших доработок и улучшения. Мы не храним загруженные файлы.")