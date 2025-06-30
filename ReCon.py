import streamlit as st
import os
import zipfile
import tempfile
from pathlib import Path
from PIL import Image
import pillow_heif
import shutil

pillow_heif.register_heif_opener()

SUPPORTED_EXTS = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff', '.heic', '.heif')

st.set_page_config(page_title="Фото-бот: Переименование и конвертация", page_icon="🖼️")

if "step" not in st.session_state:
    st.session_state["step"] = 1
if "uploaded_files" not in st.session_state:
    st.session_state["uploaded_files"] = None
if "mode" not in st.session_state:
    st.session_state["mode"] = "Переименование фото"
if "log" not in st.session_state:
    st.session_state["log"] = []
if "result_zip" not in st.session_state:
    st.session_state["result_zip"] = None
if "stats" not in st.session_state:
    st.session_state["stats"] = {}

def reset_all():
    st.session_state["step"] = 1
    st.session_state["uploaded_files"] = None
    st.session_state["mode"] = "Переименование фото"
    st.session_state["log"] = []
    st.session_state["result_zip"] = None
    st.session_state["stats"] = {}

st.title("🖼️ Фото-бот: Переименование и конвертация")

with st.expander("ℹ️ Инструкция и ответы на вопросы"):
    st.markdown("""
    **Как пользоваться ботом:**
    1. Загрузите изображения или архив.
    2. Выберите нужный режим.
    3. Дождитесь обработки и скачайте результат.

    **FAQ:**
    - *Почему не все фото обработались?*  
      Возможно, некоторые файлы были повреждены или не поддерживаются.
    - *Что делать, если архив не скачивается?*  
      Попробуйте уменьшить размер архива или разделить файлы на несколько частей.
    """)

# --- Шаг 1: Загрузка файлов ---
if st.session_state["step"] == 1:
    st.header("Шаг 1: Загрузка файлов")
    uploaded_files = st.file_uploader(
        "Загрузите изображения или zip-архив (до 200 МБ)",
        type=["jpg", "jpeg", "png", "bmp", "webp", "tiff", "heic", "heif", "zip"],
        accept_multiple_files=True,
        key="file_uploader_step1"
    )
    if uploaded_files:
        st.session_state["uploaded_files"] = uploaded_files
        if st.button("Далее", type="primary"):
            st.session_state["step"] = 2
    st.button("Начать сначала", on_click=reset_all)

# --- Шаг 2: Выбор режима ---
elif st.session_state["step"] == 2:
    st.header("Шаг 2: Выбор режима")
    mode = st.radio(
        "Выберите режим работы:",
        ["Переименование фото", "Конвертация в JPG"],
        index=0 if st.session_state["mode"] == "Переименование фото" else 1,
        key="mode_radio"
    )
    st.session_state["mode"] = mode
    col1, col2 = st.columns(2)
    with col1:
        st.button("Назад", on_click=lambda: st.session_state.update({"step": 1}))
    with col2:
        st.button("Далее", on_click=lambda: st.session_state.update({"step": 3}), type="primary")
    st.button("Начать сначала", on_click=reset_all)

# --- Шаг 3: Обработка ---
elif st.session_state["step"] == 3:
    st.header("Шаг 3: Обработка файлов")
    uploaded_files = st.session_state["uploaded_files"]
    mode = st.session_state["mode"]
    st.info(f"Режим: {mode}")
    progress_bar = st.progress(0, text="Подготовка...")
    with tempfile.TemporaryDirectory() as temp_dir:
        all_images = []
        log = []
        # --- Сбор всех файлов ---
        for uploaded in uploaded_files:
            if uploaded.name.lower().endswith(".zip"):
                zip_temp = os.path.join(temp_dir, uploaded.name)
                with open(zip_temp, "wb") as f:
                    f.write(uploaded.read())
                with zipfile.ZipFile(zip_temp, "r") as zip_ref:
                    zip_ref.extractall(temp_dir)
                extracted = [file for file in Path(temp_dir).rglob("*") if file.is_file() and file.suffix.lower() in SUPPORTED_EXTS]
                log.append(f"📦 Архив {uploaded.name}: найдено {len(extracted)} изображений.")
                all_images.extend(extracted)
            elif uploaded.name.lower().endswith(SUPPORTED_EXTS):
                img_temp = os.path.join(temp_dir, uploaded.name)
                with open(img_temp, "wb") as f:
                    f.write(uploaded.read())
                all_images.append(Path(img_temp))
                log.append(f"🖼️ Файл {uploaded.name}: добавлен.")
            else:
                log.append(f"❌ {uploaded.name}: не поддерживается.")
        if not all_images:
            st.error("Не найдено ни одного поддерживаемого изображения.")
            st.button("Назад", on_click=lambda: st.session_state.update({"step": 1}))
            st.button("Начать сначала", on_click=reset_all)
        else:
            if mode == "Переименование фото":
                exts = SUPPORTED_EXTS
                renamed = 0
                skipped = 0
                folders = sorted({img.parent for img in all_images})
                for i, folder in enumerate(folders):
                    photos = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in exts]
                    relative_folder_path = folder.relative_to(temp_dir)
                    if len(photos) == 1:
                        photo = photos[0]
                        new_name = f"1{photo.suffix.lower()}"
                        new_path = photo.parent / new_name
                        relative_photo_path = photo.relative_to(temp_dir)
                        relative_new_path = new_path.relative_to(temp_dir)
                        if new_path.exists():
                            log.append(f"Пропущено: Файл '{relative_new_path}' уже существует.")
                            skipped += 1
                        else:
                            photo.rename(new_path)
                            log.append(f"Переименовано: '{relative_photo_path}' -> '{relative_new_path}'")
                            renamed += 1
                    elif len(photos) > 1:
                        log.append(f"Пропущено: В папке '{relative_folder_path}' несколько фото.")
                        skipped += len(photos)
                    else:
                        log.append(f"Инфо: В папке '{relative_folder_path}' нет фото.")
                        skipped += 1
                    progress_bar.progress((i + 1) / len(folders), text=f"Обработано папок: {i + 1}/{len(folders)}")
                extracted_items = [p for p in Path(temp_dir).iterdir() if p.name != uploaded_files[0].name]
                zip_root = Path(temp_dir)
                if len(extracted_items) == 1 and extracted_items[0].is_dir():
                    zip_root = extracted_items[0]
                result_zip = os.path.join(temp_dir, "result_rename.zip")
                shutil.make_archive(base_name=result_zip[:-4], format='zip', root_dir=str(zip_root))
                with open(result_zip, "rb") as f:
                    st.session_state["result_zip"] = f.read()
                st.session_state["stats"] = {
                    "total": len(all_images),
                    "renamed": renamed,
                    "skipped": skipped
                }
                st.session_state["log"] = log
            else:
                converted_files = []
                errors = 0
                for i, img_path in enumerate(all_images, 1):
                    rel_path = img_path.relative_to(temp_dir)
                    out_path = os.path.join(temp_dir, str(rel_path.with_suffix('.jpg')))
                    out_dir = os.path.dirname(out_path)
                    os.makedirs(out_dir, exist_ok=True)
                    try:
                        img = Image.open(img_path)
                        icc_profile = img.info.get('icc_profile')
                        img = img.convert("RGB")
                        img.save(out_path, "JPEG", quality=100, optimize=True, progressive=True, icc_profile=icc_profile)
                        converted_files.append((out_path, rel_path.with_suffix('.jpg')))
                        log.append(f"✅ {rel_path} → {rel_path.with_suffix('.jpg')}")
                    except Exception as e:
                        log.append(f"❌ {rel_path}: ошибка конвертации ({e})")
                        errors += 1
                    progress_bar.progress(i / len(all_images), text=f"Обработано файлов: {i}/{len(all_images)}")
                if converted_files:
                    result_zip = os.path.join(temp_dir, "result_convert.zip")
                    with zipfile.ZipFile(result_zip, "w") as zipf:
                        for src, rel in converted_files:
                            zipf.write(src, arcname=rel)
                    with open(result_zip, "rb") as f:
                        st.session_state["result_zip"] = f.read()
                    st.session_state["stats"] = {
                        "total": len(all_images),
                        "converted": len(converted_files),
                        "errors": errors
                    }
                    st.session_state["log"] = log
                else:
                    st.error("Не удалось конвертировать ни одного изображения.")
                    st.session_state["log"] = log
            st.session_state["step"] = 4
    st.button("Назад", on_click=lambda: st.session_state.update({"step": 2}))
    st.button("Начать сначала", on_click=reset_all)

# --- Шаг 4: Скачивание результата ---
elif st.session_state["step"] == 4:
    st.header("Шаг 4: Скачивание результата")
    stats = st.session_state["stats"]
    mode = st.session_state["mode"]
    if mode == "Переименование фото":
        st.success(f"Готово! Переименовано: {stats.get('renamed', 0)} из {stats.get('total', 0)} папок. Пропущено: {stats.get('skipped', 0)}")
        st.download_button(
            label="📥 Скачать архив с переименованными фото",
            data=st.session_state["result_zip"],
            file_name="renamed_photos.zip",
            mime="application/zip"
        )
    else:
        st.success(f"Готово! Конвертировано: {stats.get('converted', 0)} из {stats.get('total', 0)} файлов. Ошибок: {stats.get('errors', 0)}")
        st.download_button(
            label="📥 Скачать архив с JPG",
            data=st.session_state["result_zip"],
            file_name="converted_images.zip",
            mime="application/zip"
        )
    with st.expander("Показать лог обработки"):
        st.text_area("Лог:", value="\n".join(st.session_state["log"]), height=300, disabled=True)
    st.button("Начать сначала", on_click=reset_all) 
