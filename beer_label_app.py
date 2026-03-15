import json
import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from PIL import Image, ImageDraw, ImageFont, ImageTk, ImageWin
import win32print
import win32ui

# Для генерации штрихкода
import barcode
from barcode.writer import ImageWriter

# Конфигурация
PRINTER_NAME = "Xprinter XP-365B"
FONT_PATH = "arial.ttf"  # не используется напрямую, оставлено для совместимости

# Путь к файлу данных
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "beers_data.json")


class BeerDialog:
    """Диалог добавления/редактирования сорта с полем для штрихкода."""
    def __init__(self, parent, beer=None):
        self.parent = parent
        self.beer = beer
        self.result = None

        self.top = tk.Toplevel(parent)
        self.top.title("Добавление сорта" if beer is None else "Редактирование сорта")
        self.top.geometry("550x450")
        self.top.transient(parent)
        self.top.grab_set()
        self.top.resizable(False, False)

        style = ttk.Style()
        style.configure('Large.TLabel', font=('Arial', 12))
        style.configure('Large.TEntry', font=('Arial', 12), padding=5)
        style.configure('Large.TButton', font=('Arial', 12), padding=8)

        # Основные поля
        fields = [("Название", True), ("Тип", True), ("Цена", True), ("Кран", True)]
        self.entries = {}

        # Фрейм для полей ввода
        input_frame = ttk.Frame(self.top, padding="20 20 20 10")
        input_frame.pack(fill=tk.BOTH, expand=True)

        row = 0
        for label, required in fields:
            # Метка с выравниванием вправо
            ttk.Label(input_frame, text=label + ":", style='Large.TLabel').grid(
                row=row, column=0, padx=5, pady=8, sticky=tk.E
            )
            entry = ttk.Entry(input_frame, width=40, style='Large.TEntry')
            entry.grid(row=row, column=1, padx=5, pady=8, sticky=tk.W)
            if beer and label in beer:
                entry.insert(0, beer[label])
            self.entries[label] = entry
            row += 1

        # Поле для штрихкода
        ttk.Label(input_frame, text="Штрихкод:", style='Large.TLabel').grid(
            row=row, column=0, padx=5, pady=8, sticky=tk.E
        )
        self.barcode_entry = ttk.Entry(input_frame, width=40, style='Large.TEntry')
        self.barcode_entry.grid(row=row, column=1, padx=5, pady=8, sticky=tk.W)
        if beer and "Штрихкод" in beer:
            self.barcode_entry.insert(0, beer["Штрихкод"])
        row += 1

        # Фрейм для кнопок
        btn_frame = ttk.Frame(self.top)
        btn_frame.pack(fill=tk.X, padx=20, pady=15)

        ttk.Button(btn_frame, text="Сохранить", command=self.save, style='Large.TButton').pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Отмена", command=self.top.destroy, style='Large.TButton').pack(side=tk.LEFT, padx=10)

        self.top.wait_window()

    def save(self):
        data = {}
        for field, entry in self.entries.items():
            value = entry.get().strip()
            if not value:
                messagebox.showwarning("Предупреждение", f"Поле '{field}' обязательно")
                return
            data[field] = value

        barcode_value = self.barcode_entry.get().strip()
        if barcode_value:
            data["Штрихкод"] = barcode_value
        else:
            data.pop("Штрихкод", None)

        self.result = data
        self.top.destroy()


class PhotoPrintDialog:
    """Диалог выбора области фото и печати на этикетку."""
    def __init__(self, parent, image_path, printer_name):
        self.parent = parent
        self.image_path = image_path
        self.printer_name = printer_name

        self.original_image = Image.open(image_path).convert("RGB")
        self.orig_width, self.orig_height = self.original_image.size

        # Параметры отображения
        self.scale = 1.0
        self.img_x = 0
        self.img_y = 0
        self.canvas_width = 800
        self.canvas_height = 600
        self.label_width = 580      # ширина этикетки в пикселях (для печати)
        self.label_height = 400     # высота этикетки
        self.rect_id = None
        self.drag_data = {"x": 0, "y": 0, "item": None}

        self.top = tk.Toplevel(parent)
        self.top.title("Печать фото")
        self.top.geometry("900x700")
        self.top.transient(parent)
        self.top.grab_set()

        self.create_widgets()
        self.load_image()
        self.center_rectangle()
        self.top.bind("<MouseWheel>", self.on_mousewheel)

    def create_widgets(self):
        # Верхняя панель с кнопками
        top_frame = ttk.Frame(self.top)
        top_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(top_frame, text="Выбрать другое фото", command=self.choose_photo).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="Печать", command=self.print_photo).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="Отмена", command=self.top.destroy).pack(side=tk.LEFT, padx=2)

        # Основная область с прокруткой
        main_frame = ttk.Frame(self.top)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.h_scroll = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL)
        self.v_scroll = ttk.Scrollbar(main_frame, orient=tk.VERTICAL)

        self.canvas = tk.Canvas(main_frame,
                                width=self.canvas_width,
                                height=self.canvas_height,
                                xscrollcommand=self.h_scroll.set,
                                yscrollcommand=self.v_scroll.set,
                                bg='gray')
        self.canvas.grid(row=0, column=0, sticky='nsew')

        self.h_scroll.grid(row=1, column=0, sticky='ew')
        self.v_scroll.grid(row=0, column=1, sticky='ns')

        self.h_scroll.config(command=self.canvas.xview)
        self.v_scroll.config(command=self.canvas.yview)

        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Привязка событий мыши для прямоугольника
        self.canvas.tag_bind("rect", "<ButtonPress-1>", self.on_rect_press)
        self.canvas.tag_bind("rect", "<B1-Motion>", self.on_rect_drag)
        self.canvas.tag_bind("rect", "<ButtonRelease-1>", self.on_rect_release)

    def choose_photo(self):
        path = filedialog.askopenfilename(
            title="Выберите фото",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.gif *.tiff")]
        )
        if path:
            self.image_path = path
            self.original_image = Image.open(path).convert("RGB")
            self.orig_width, self.orig_height = self.original_image.size
            self.load_image()
            self.center_rectangle()

    def load_image(self):
        """Масштабирует и отображает изображение на canvas с учётом self.scale и смещения."""
        # Вычисляем размеры для отображения
        display_width = int(self.orig_width * self.scale)
        display_height = int(self.orig_height * self.scale)

        # Изменяем размер оригинального изображения для отображения (сохраняем качество)
        resized = self.original_image.resize((display_width, display_height), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized)

        # Обновляем область прокрутки canvas
        self.canvas.config(scrollregion=(
            min(self.img_x, 0),
            min(self.img_y, 0),
            max(self.img_x + display_width, self.canvas_width),
            max(self.img_y + display_height, self.canvas_height)
        ))

        # Удаляем старое изображение, если есть
        self.canvas.delete("image")
        # Создаём новое
        self.canvas.create_image(self.img_x, self.img_y,
                                 anchor='nw',
                                 image=self.tk_image,
                                 tags="image")

        # Перемещаем прямоугольник поверх изображения
        if self.rect_id:
            self.canvas.tag_raise("rect")
        else:
            self.create_rectangle()

        # Ограничиваем прямоугольник в пределах изображения
        self.clamp_rectangle()

    def create_rectangle(self):
        """Создаёт прямоугольник размером с этикетку в центре текущего вида."""
        # Начальная позиция: центр canvas
        cx = self.canvas.canvasx(self.canvas_width // 2)
        cy = self.canvas.canvasy(self.canvas_height // 2)
        x1 = cx - self.label_width // 2
        y1 = cy - self.label_height // 2
        x2 = x1 + self.label_width
        y2 = y1 + self.label_height

        self.rect_id = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline='red', width=3,
            tags=("rect",)
        )
        self.clamp_rectangle()

    def center_rectangle(self):
        """Перемещает прямоугольник в центр видимой области canvas."""
        if not self.rect_id:
            return
        cx = self.canvas.canvasx(self.canvas_width // 2)
        cy = self.canvas.canvasy(self.canvas_height // 2)
        x1 = cx - self.label_width // 2
        y1 = cy - self.label_height // 2
        x2 = x1 + self.label_width
        y2 = y1 + self.label_height
        self.canvas.coords(self.rect_id, x1, y1, x2, y2)
        self.clamp_rectangle()

    def clamp_rectangle(self):
        """Ограничивает прямоугольник, чтобы он не выходил за границы изображения."""
        if not self.rect_id:
            return
        x1, y1, x2, y2 = self.canvas.coords(self.rect_id)
        # Левый верхний угол изображения
        img_left = self.img_x
        img_top = self.img_y
        img_right = self.img_x + int(self.orig_width * self.scale)
        img_bottom = self.img_y + int(self.orig_height * self.scale)

        # Корректируем
        if x1 < img_left:
            dx = img_left - x1
            x1 += dx
            x2 += dx
        if y1 < img_top:
            dy = img_top - y1
            y1 += dy
            y2 += dy
        if x2 > img_right:
            dx = x2 - img_right
            x1 -= dx
            x2 -= dx
        if y2 > img_bottom:
            dy = y2 - img_bottom
            y1 -= dy
            y2 -= dy

        self.canvas.coords(self.rect_id, x1, y1, x2, y2)

    def on_rect_press(self, event):
        """Захват прямоугольника мышью."""
        self.drag_data["x"] = self.canvas.canvasx(event.x)
        self.drag_data["y"] = self.canvas.canvasy(event.y)
        self.drag_data["item"] = self.rect_id

    def on_rect_drag(self, event):
        """Перемещение прямоугольника."""
        if not self.drag_data["item"]:
            return
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        dx = x - self.drag_data["x"]
        dy = y - self.drag_data["y"]
        self.canvas.move(self.rect_id, dx, dy)
        self.drag_data["x"] = x
        self.drag_data["y"] = y
        self.clamp_rectangle()

    def on_rect_release(self, event):
        self.drag_data["item"] = None

    def on_mousewheel(self, event):
        """Масштабирование изображения колёсиком мыши (относительно центра canvas)."""
        # Коэффициент масштабирования
        factor = 1.1 if event.delta > 0 else 0.9
        new_scale = self.scale * factor

        # Ограничим слишком маленький или большой масштаб
        if new_scale < 0.05 or new_scale > 5.0:
            return

        # Сохраняем точку в центре canvas (в координатах canvas)
        cx = self.canvas.canvasx(self.canvas_width // 2)
        cy = self.canvas.canvasy(self.canvas_height // 2)

        # Вычисляем, какой точке исходного изображения соответствует центр canvas
        orig_cx = (cx - self.img_x) / self.scale
        orig_cy = (cy - self.img_y) / self.scale

        # Обновляем масштаб
        self.scale = new_scale

        # Новые размеры изображения
        new_disp_width = int(self.orig_width * self.scale)
        new_disp_height = int(self.orig_height * self.scale)

        # Новое смещение, чтобы центр остался на том же месте
        self.img_x = cx - orig_cx * self.scale
        self.img_y = cy - orig_cy * self.scale

        # Перезагружаем изображение с новыми параметрами
        self.load_image()

    def get_crop_region(self):
        """Возвращает область исходного изображения (left, top, right, bottom), соответствующую прямоугольнику."""
        x1, y1, x2, y2 = self.canvas.coords(self.rect_id)

        # Преобразуем canvas-координаты в координаты исходного изображения
        left = int((x1 - self.img_x) / self.scale)
        top = int((y1 - self.img_y) / self.scale)
        right = int((x2 - self.img_x) / self.scale)
        bottom = int((y2 - self.img_y) / self.scale)

        # Обрезаем по границам оригинального изображения
        left = max(0, min(left, self.orig_width))
        top = max(0, min(top, self.orig_height))
        right = max(0, min(right, self.orig_width))
        bottom = max(0, min(bottom, self.orig_height))

        return (left, top, right, bottom)

    def print_photo(self):
        """Вырезает выделенную область и печатает её как этикетку."""
        try:
            crop_box = self.get_crop_region()
            if crop_box[2] - crop_box[0] <= 0 or crop_box[3] - crop_box[1] <= 0:
                messagebox.showerror("Ошибка", "Выделена пустая область")
                return

            # Вырезаем область из оригинального изображения
            cropped = self.original_image.crop(crop_box)

            # Масштабируем до размера этикетки (580x400) - растягиваем
            img_to_print = cropped.resize((self.label_width, self.label_height), Image.Resampling.LANCZOS)

            # Печатаем через win32print
            hdc = win32ui.CreateDC()
            hdc.CreatePrinterDC(self.printer_name)
            hdc.StartDoc("Photo Print")
            hdc.StartPage()
            dib = ImageWin.Dib(img_to_print)
            dib.draw(hdc.GetHandleOutput(), (0, 0, img_to_print.width, img_to_print.height))
            hdc.EndPage()
            hdc.EndDoc()
            hdc.DeleteDC()

            messagebox.showinfo("Печать", "Фото отправлено на печать")
        except Exception as e:
            messagebox.showerror("Ошибка печати", str(e))


class MultiPrintDialog:
    """Диалог выбора нескольких сортов и количества копий для печати."""
    def __init__(self, parent, beers, printer_name, label_generator):
        """
        parent: родительское окно
        beers: список всех сортов
        printer_name: имя принтера
        label_generator: функция generate_label(beer) -> PIL Image
        """
        self.parent = parent
        self.beers = beers
        self.printer_name = printer_name
        self.generate_label = label_generator

        self.selected = {}  # beer -> IntVar(количество)

        self.top = tk.Toplevel(parent)
        self.top.title("Печать нескольких этикеток")
        self.top.geometry("600x500")
        self.top.transient(parent)
        self.top.grab_set()

        self.create_widgets()

    def create_widgets(self):
        # Инструкция
        ttk.Label(self.top, text="Выберите сорта и укажите количество копий:", font=('Arial', 12)).pack(pady=10)

        # Фрейм с прокруткой для списка
        frame = ttk.Frame(self.top)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        canvas = tk.Canvas(frame, borderwidth=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Заполняем список
        for beer in self.beers:
            var = tk.IntVar(value=0)  # по умолчанию 0 копий
            self.selected[beer["Название"]] = (beer, var)

            row = ttk.Frame(scrollable_frame)
            row.pack(fill=tk.X, pady=2)

            chk = ttk.Checkbutton(row, variable=var, command=lambda b=beer, v=var: self.on_check(b, v))
            chk.pack(side=tk.LEFT)

            label_text = f"{beer.get('Название', '')} (кран {beer.get('Кран', '')})"
            ttk.Label(row, text=label_text, font=('Arial', 11)).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

            # Поле ввода количества (только цифры)
            entry = ttk.Entry(row, width=5, textvariable=var, validate='key')
            entry['validatecommand'] = (entry.register(self.validate_int), '%P')
            entry.pack(side=tk.RIGHT, padx=5)

        # Кнопки внизу
        btn_frame = ttk.Frame(self.top)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text="Печать", command=self.print_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Отмена", command=self.top.destroy).pack(side=tk.LEFT, padx=5)

    def validate_int(self, value):
        if value == "":
            return True
        try:
            int(value)
            return True
        except:
            return False

    def on_check(self, beer, var):
        """При клике на чекбокс устанавливаем мин. значение 1, если включено."""
        if var.get() == 0:
            # Если чекбокс снят, оставляем 0
            pass
        else:
            # Если установлен и значение 0, меняем на 1
            if var.get() == 0:
                var.set(1)

    def print_selected(self):
        """Печатает выбранные сорта."""
        to_print = []
        for name, (beer, var) in self.selected.items():
            count = var.get()
            if count > 0:
                to_print.append((beer, count))

        if not to_print:
            messagebox.showwarning("Предупреждение", "Не выбрано ни одного сорта")
            return

        # Подтверждение
        msg = "Будут напечатаны:\n"
        for beer, cnt in to_print:
            msg += f"  {beer['Название']} - {cnt} шт.\n"
        if not messagebox.askyesno("Подтверждение", msg + "\nПродолжить?"):
            return

        # Печать
        try:
            hdc = win32ui.CreateDC()
            hdc.CreatePrinterDC(self.printer_name)

            for beer, cnt in to_print:
                img = self.generate_label(beer)
                for i in range(cnt):
                    hdc.StartDoc(f"Beer Label - {beer['Название']} #{i+1}")
                    hdc.StartPage()
                    dib = ImageWin.Dib(img)
                    dib.draw(hdc.GetHandleOutput(), (0, 0, img.width, img.height))
                    hdc.EndPage()
                    hdc.EndDoc()
            hdc.DeleteDC()
            messagebox.showinfo("Печать", "Все этикетки отправлены на печать")
            self.top.destroy()
        except Exception as e:
            messagebox.showerror("Ошибка печати", str(e))


class BeerLabelApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CultBeerLabelApp")
        self.root.state('zoomed')  # полноэкранный режим

        # Установка иконки (если есть файл beer.ico или beer.png в папке программы)
        self.set_icon()

        self.beers = self.load_data()
        self.sort_beers()

        # NEW: путь к выбранному пользователем шрифту
        self.selected_font_path = self.load_font_path()

        self.filter_text = tk.StringVar()
        self.selected_beer = None
        self.displayed_beers = []
        self.label_image = None

        self.setup_styles()
        self.create_widgets()
        self.refresh_list()

    def set_icon(self):
        """Пытается установить иконку окна из файла beer_icon.ico."""
        icon_path = os.path.join(BASE_DIR, "beer_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
                return
            except:
                pass
        # Попробуем PNG
        png_path = os.path.join(BASE_DIR, "beer.png")
        if os.path.exists(png_path):
            try:
                img = tk.PhotoImage(file=png_path)
                self.root.iconphoto(False, img)
            except:
                pass

    def setup_styles(self):
        style = ttk.Style()
        style.configure('Large.TButton', font=('Arial', 12), padding=8)
        style.configure('Large.TLabel', font=('Arial', 11))
        style.configure('Large.TEntry', font=('Arial', 11), padding=5)

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for beer in data:
                    # Удаляем устаревшие ключи, связанные с фото
                    beer.pop("Изображение", None)
                    beer.pop("Область", None)
                    beer.pop("Приветствие", None)
                    if "Кран" not in beer:
                        beer["Кран"] = ""
                return data
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить данные: {e}")
                return []
        return []

    def save_data(self):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.beers, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить данные: {e}")

    def sort_beers(self):
        def key_func(beer):
            k = beer.get("Кран", "")
            try:
                return (0, int(k))
            except:
                return (1, k)
        self.beers.sort(key=key_func)

    # NEW: загрузка и сохранение пути к шрифту
    def load_font_path(self):
        """Загружает путь к выбранному шрифту из файла font_path.txt."""
        font_file = os.path.join(BASE_DIR, "font_path.txt")
        if os.path.exists(font_file):
            try:
                with open(font_file, "r", encoding="utf-8") as f:
                    path = f.read().strip()
                    if os.path.exists(path):
                        return path
            except:
                pass
        # Если файла нет или он повреждён, используем стандартный Arial (или None)
        return "arial.ttf"

    def save_font_path(self, path):
        """Сохраняет путь к шрифту в файл font_path.txt."""
        font_file = os.path.join(BASE_DIR, "font_path.txt")
        try:
            with open(font_file, "w", encoding="utf-8") as f:
                f.write(path)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить путь к шрифту: {e}")

    def choose_font(self):
        """Открывает диалог выбора TTF-файла и сохраняет путь."""
        path = filedialog.askopenfilename(
            title="Выберите файл шрифта",
            filetypes=[("TrueType fonts", "*.ttf"), ("All files", "*.*")]
        )
        if path:
            self.selected_font_path = path
            self.save_font_path(path)
            # Если есть выбранный сорт, обновим предпросмотр с новым шрифтом
            if self.selected_beer:
                self.show_label()

    def create_widgets(self):
        # Верхняя панель с поиском
        top_frame = ttk.Frame(self.root, padding=5)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="Поиск:", style='Large.TLabel').pack(side=tk.LEFT, padx=5)
        ttk.Entry(top_frame, textvariable=self.filter_text, width=30, style='Large.TEntry').pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Найти", command=self.search, style='Large.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Сброс", command=self.reset_search, style='Large.TButton').pack(side=tk.LEFT, padx=5)

        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Левая панель - список и кнопки
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=1)

        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Arial", 14))
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        self.listbox.bind('<<ListboxSelect>>', self.on_select)
        self.listbox.bind('<Return>', self.print_label_on_enter)

        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text="Добавить", command=self.add_beer_dialog, style='Large.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Редактировать", command=self.edit_beer, style='Large.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Удалить", command=self.delete_beer, style='Large.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Показать этикетку", command=self.show_label, style='Large.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Печать", command=self.print_label, style='Large.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Напечатать фото", command=self.print_photo, style='Large.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Печать нескольких", command=self.print_multiple, style='Large.TButton').pack(side=tk.LEFT, padx=2)
        # NEW: кнопка выбора шрифта
        ttk.Button(btn_frame, text="Выбрать шрифт", command=self.choose_font, style='Large.TButton').pack(side=tk.LEFT, padx=2)

        # Правая панель - изображение этикетки
        right_frame = ttk.Frame(main_pane, relief=tk.SUNKEN, borderwidth=2)
        main_pane.add(right_frame, weight=2)

        self.image_label = ttk.Label(right_frame, text="Здесь будет этикетка", anchor=tk.CENTER, style='Large.TLabel')
        self.image_label.pack(fill=tk.BOTH, expand=True)

    def refresh_list(self, filter_text=None):
        self.listbox.delete(0, tk.END)
        self.displayed_beers = []
        if filter_text:
            ft = filter_text.lower()
            filtered = [b for b in self.beers if ft in b.get("Название", "").lower() or ft in b.get("Тип", "").lower() or ft in b.get("Кран", "").lower()]
        else:
            filtered = self.beers

        self.displayed_beers = filtered
        for beer in filtered:
            self.listbox.insert(tk.END, beer.get("Название", ""))

        if filtered:
            self.listbox.selection_set(0)
            self.on_select()

    def search(self):
        text = self.filter_text.get().strip()
        self.refresh_list(text if text else None)

    def reset_search(self):
        self.filter_text.set("")
        self.refresh_list()

    def on_select(self, event=None):
        selection = self.listbox.curselection()
        if selection and self.displayed_beers:
            index = selection[0]
            self.selected_beer = self.displayed_beers[index]

    def print_label_on_enter(self, event):
        self.print_label()

    def add_beer_dialog(self):
        dlg = BeerDialog(self.root, beer=None)
        if dlg.result:
            self.beers.append(dlg.result)
            self.sort_beers()
            self.save_data()
            self.refresh_list(self.filter_text.get().strip() or None)

    def edit_beer(self):
        if not self.selected_beer:
            messagebox.showinfo("Информация", "Выберите сорт для редактирования")
            return

        dlg = BeerDialog(self.root, beer=self.selected_beer)
        if dlg.result:
            index = self.beers.index(self.selected_beer)
            self.beers[index] = dlg.result
            self.sort_beers()
            self.save_data()
            self.selected_beer = dlg.result
            self.refresh_list(self.filter_text.get().strip() or None)
            self.show_label()

    def delete_beer(self):
        if not self.selected_beer:
            messagebox.showinfo("Информация", "Выберите сорт для удаления")
            return

        confirm = messagebox.askyesno("Подтверждение", f"Удалить сорт '{self.selected_beer.get('Название', '')}'?")
        if confirm:
            self.beers.remove(self.selected_beer)
            self.save_data()
            self.selected_beer = None
            self.refresh_list(self.filter_text.get().strip() or None)
            self.image_label.config(image='', text='Этикетка удалена')

    def generate_barcode(self, data):
        """Генерирует изображение штрихкода Code128 из строки data."""
        if not data:
            return None
        try:
            barcode_obj = barcode.get('code128', data, writer=ImageWriter())
            options = {
                'write_text': True,
                'module_width': 1.2,
                'module_height': 30.0,
                'quiet_zone': 3,
                'font_size': 30,
                'text_distance': 13
            }
            img = barcode_obj.render(writer_options=options)
            return img
        except Exception as e:
            print(f"Ошибка генерации штрихкода: {e}")
            return None

    # ИЗМЕНЕНИЯ: generate_label использует выбранный шрифт
    def generate_label(self, beer):
        """Создаёт этикетку: текст вверху, штрихкод внизу с динамическим отступом."""
        width, height = 580, 400
        img = Image.new("RGB", (width, height), "#000000")
        draw = ImageDraw.Draw(img)

        # Функция загрузки шрифта (теперь использует self.selected_font_path)
        def load_font(size, is_bold=False):
            # Если пользователь выбрал свой шрифт и он существует, используем его
            if self.selected_font_path and os.path.exists(self.selected_font_path):
                try:
                    return ImageFont.truetype(self.selected_font_path, size)
                except:
                    pass  # если не удалось загрузить, пробуем стандартные
            # Запасные варианты (как в исходном коде)
            try:
                if is_bold:
                    return ImageFont.truetype("arialbd.ttf", size)
                else:
                    return ImageFont.truetype("arial.ttf", size)
            except:
                return ImageFont.load_default()

        # Загружаем шрифты согласно настройкам
        font_logo = load_font(54, is_bold=True)
        font_title = load_font(21, is_bold=True)
        font_type = load_font(30, is_bold=False)
        font_price = load_font(30, is_bold=True)
        font_note = load_font(30, is_bold=False)

        left_margin = 20
        top_margin = 20
        line_spacing = 9
        y = top_margin

        def draw_line(text, font):
            nonlocal y
            if text:
                draw.text((left_margin, y), text, font=font, fill="white")
                bbox = draw.textbbox((0, 0), text, font=font)
                line_height = bbox[3] - bbox[1]
                y += line_height + line_spacing

        # Рисуем текстовые поля
        draw_line("КультПива", font_logo)
        draw_line(beer.get("Название", ""), font_title)
        draw_line(beer.get("Тип", ""), font_type)
        draw_line(f"Цена за 1л: {beer.get('Цена', '')} ₽", font_price)
        draw_line(f"Кран: {beer.get('Кран', '')}", font_note)

        # Штрихкод
        barcode_data = beer.get("Штрихкод", "")
        if barcode_data:
            barcode_img = self.generate_barcode(barcode_data)
            if barcode_img:
                max_barcode_height = 100
                orig_w, orig_h = barcode_img.size

                scale = min((width - 2 * left_margin) / orig_w, max_barcode_height / orig_h)
                new_w = int(orig_w * scale)
                new_h = int(orig_h * scale)
                resized_barcode = barcode_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                small_margin = 100
                bottom_margin = 105
                proposed_y = y + small_margin
                if proposed_y + new_h <= height - bottom_margin:
                    paste_y = proposed_y
                else:
                    paste_y = height - new_h - bottom_margin

                paste_x = 150
                img.paste(resized_barcode, (paste_x, paste_y))

        return img

    def show_label(self):
        if not self.selected_beer:
            messagebox.showinfo("Информация", "Выберите сорт")
            return

        img = self.generate_label(self.selected_beer)
        img_tk = ImageTk.PhotoImage(img)
        self.image_label.config(image=img_tk, text='')
        self.image_label.image = img_tk

    def print_label(self):
        if not self.selected_beer:
            messagebox.showinfo("Информация", "Выберите сорт")
            return

        img = self.generate_label(self.selected_beer)

        try:
            hprinter = win32print.OpenPrinter(PRINTER_NAME)
            hdc = win32ui.CreateDC()
            hdc.CreatePrinterDC(PRINTER_NAME)
            hdc.StartDoc("Beer Label")
            hdc.StartPage()
            dib = ImageWin.Dib(img)
            dib.draw(hdc.GetHandleOutput(), (0, 0, img.width, img.height))
            hdc.EndPage()
            hdc.EndDoc()
            hdc.DeleteDC()
            messagebox.showinfo("Печать", "Этикетка отправлена на печать")
        except Exception as e:
            messagebox.showerror("Ошибка печати", str(e))

    def print_photo(self):
        """Открывает диалог печати фото."""
        # Запрашиваем файл
        file_path = filedialog.askopenfilename(
            title="Выберите фото для печати",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.gif *.tiff")]
        )
        if not file_path:
            return

        # Открываем диалог с фото
        PhotoPrintDialog(self.root, file_path, PRINTER_NAME)

    def print_multiple(self):
        """Открывает диалог печати нескольких этикеток."""
        if not self.beers:
            messagebox.showinfo("Информация", "Нет сортов для печати")
            return
        MultiPrintDialog(self.root, self.beers, PRINTER_NAME, self.generate_label)


if __name__ == "__main__":
    root = tk.Tk()
    app = BeerLabelApp(root)
    root.mainloop()