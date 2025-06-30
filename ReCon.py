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
st.title("🖼️ Фото-бот: Переименование и конвертация")

mode = st.radio(
    "Выберите режим работы:",
    ["Переименование фото", "Конвертация в JPG"]
)

st.markdown(
    """
    <small>Загрузите изображения или zip-архив с папками и фото.<br>
    <b>Переименование:</b> В каждой папке фото будет переименовано в <code>1.jpg</code>.<br>
    <b>Конвертация:</b> Все изображения будут конвертированы в <b>JPG</b> с максимальным качеством.<br>
    Поддерживаются форматы: JPG, PNG, BMP, WEBP, TIFF, HEIC/HEIF.</small>
    """, unsafe_allow_html=True
)

uploaded_files = st.file_uploader(
    "Загрузите изображения или zip-архив (до 200 МБ)",
    type=["jpg", "jpeg", "png", "bmp", "webp", "tiff", "heic", "heif", "zip"],
    accept_multiple_files=True
)

if "log" not in st.session_state:
    st.session_state.log = []
if "result_zip" not in st.session_state:
    st.session_state.result_zip = None
if "stats" not in st.session_state:
    st.session_state.stats = {}

def reset_state():
    st.session_state.log = []
    st.session_state.result_zip = None
    st.session_state.stats = {}

if st.button("Сбросить", type="primary"):
    reset_state()

def extract_images_from_zip(zip_file, temp_dir):
    extracted = []
    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        zip_ref.extractall(temp_dir)
    for file in Path(temp_dir).rglob("*"):
        if file.is_file() and file.suffix.lower() in SUPPORTED_EXTS:
            extracted.append(file)
    return extracted

def convert_to_jpg(src_path, dst_path):
    try:
        img = Image.open(src_path)
        icc_profile = img.info.get('icc_profile')
        img = img.convert("RGB")
        img.save(dst_path, "JPEG", quality=100, optimize=True, progressive=True, icc_profile=icc_profile)
        return True, ""
    except Exception as e:
        return False, str(e)

def make_zip_with_structure(files, root_dir, zip_path):
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for src, rel in files:
            zipf.write(src, arcname=rel)

def make_zip_with_folders(root_dir, zip_path):
    # Сохраняет структуру папок, включая пустые
    shutil.make_archive(base_name=str(zip_path)[:-4], format='zip', root_dir=str(root_dir))

def clear_temp_dir(temp_dir):
    for root, dirs, files in os.walk(temp_dir, topdown=False):
        for name in files:
            try:
                os.remove(os.path.join(root, name))
            except Exception:
                pass
        for name in dirs:
            try:
                os.rmdir(os.path.join(root, name))
            except Exception:
                pass

if uploaded_files:
    with st.spinner("Обработка файлов..."):
        with tempfile.TemporaryDirectory() as temp_dir:
            all_images = []
            log = []
            # --- Сбор всех файлов ---
            for uploaded in uploaded_files:
                if uploaded.name.lower().endswith(".zip"):
                    zip_temp = os.path.join(temp_dir, uploaded.name)
                    with open(zip_temp, "wb") as f:
                        f.write(uploaded.read())
                    extracted = extract_images_from_zip(zip_temp, temp_dir)
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
            else:
                if mode == "Переименование фото":
                    # --- Переименование ---
                    exts = SUPPORTED_EXTS
                    renamed = 0
                    skipped = 0
                    folders = sorted({img.parent for img in all_images})
                    for folder in folders:
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
                    # Архивируем с сохранением структуры, включая пустые папки
                    extracted_items = [p for p in Path(temp_dir).iterdir() if p.name != uploaded_files[0].name]
                    zip_root = Path(temp_dir)
                    if len(extracted_items) == 1 and extracted_items[0].is_dir():
                        zip_root = extracted_items[0]
                    result_zip = os.path.join(temp_dir, "result_rename.zip")
                    make_zip_with_folders(zip_root, result_zip)
                    with open(result_zip, "rb") as f:
                        st.session_state.result_zip = f.read()
                    st.session_state.stats = {
                        "total": len(all_images),
                        "renamed": renamed,
                        "skipped": skipped
                    }
                    st.session_state.log = log
                else:
                    # --- Конвертация ---
                    converted_files = []
                    errors = 0
                    for i, img_path in enumerate(all_images, 1):
                        rel_path = img_path.relative_to(temp_dir)
                        out_path = os.path.join(temp_dir, str(rel_path.with_suffix('.jpg')))
                        out_dir = os.path.dirname(out_path)
                        os.makedirs(out_dir, exist_ok=True)
                        ok, err = convert_to_jpg(img_path, out_path)
                        if ok:
                            converted_files.append((out_path, rel_path.with_suffix('.jpg')))
                            log.append(f"✅ {rel_path} → {rel_path.with_suffix('.jpg')}")
                        else:
                            log.append(f"❌ {rel_path}: ошибка конвертации ({err})")
                            errors += 1
                    if converted_files:
                        result_zip = os.path.join(temp_dir, "result_convert.zip")
                        make_zip_with_structure(converted_files, temp_dir, result_zip)
                        with open(result_zip, "rb") as f:
                            st.session_state.result_zip = f.read()
                        st.session_state.stats = {
                            "total": len(all_images),
                            "converted": len(converted_files),
                            "errors": errors
                        }
                        st.session_state.log = log
                    else:
                        st.error("Не удалось конвертировать ни одного изображения.")
                        st.session_state.log = log

if st.session_state.result_zip:
    stats = st.session_state.stats
    if mode == "Переименование фото":
        st.success(f"Готово! Переименовано: {stats.get('renamed', 0)} из {stats.get('total', 0)} папок. Пропущено: {stats.get('skipped', 0)}")
        st.download_button(
            label="📥 Скачать архив с переименованными фото",
            data=st.session_state.result_zip,
            file_name="renamed_photos.zip",
            mime="application/zip"
        )
    else:
        st.success(f"Готово! Конвертировано: {stats.get('converted', 0)} из {stats.get('total', 0)} файлов. Ошибок: {stats.get('errors', 0)}")
        st.download_button(
            label="📥 Скачать архив с JPG",
            data=st.session_state.result_zip,
            file_name="converted_images.zip",
            mime="application/zip"
        )
    with st.expander("Показать лог обработки"):
        st.text_area("Лог:", value="\n".join(st.session_state.log), height=300, disabled=True)