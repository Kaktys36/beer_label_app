import json
import os
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from io import BytesIO
from PIL import *
import win32print
import win32ui

# Конфигурация
PRINTER_NAME = "Xprinter XP-365B"  # Можно изменить на другой принтер
FONT_PATH = "arial.ttf"  # Системный шрифт Arial

# Путь к файлу данных
if getattr(sys, 'frozen', False):
    # Если запущено как exe, данные сохраняем рядом с exe
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "beers_data.json")


class BeerLabelApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Управление этикетками пива")
        self.root.geometry("900x700")

        # Загрузка данных
        self.beers = self.load_data()

        # Переменные
        self.filter_text = tk.StringVar()
        self.selected_beer = None
        self.label_image = None  # Для хранения ссылки на фото

        # Создание интерфейса
        self.create_widgets()
        self.refresh_list()

    def load_data(self):
        """Загружает данные из JSON файла"""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить данные: {e}")
                return []
        return []

    def save_data(self):
        """Сохраняет данные в JSON файл"""
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.beers, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить данные: {e}")

    def create_widgets(self):
        # Верхняя панель с поиском
        top_frame = ttk.Frame(self.root, padding=5)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="Поиск:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(top_frame, textvariable=self.filter_text, width=30).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Найти", command=self.search).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Сброс", command=self.reset_search).pack(side=tk.LEFT, padx=5)

        # Основная область: список слева, изображение справа
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Левая панель - список и кнопки
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=1)

        # Список сортов
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Arial", 10))
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        self.listbox.bind('<<ListboxSelect>>', self.on_select)

        # Кнопки управления списком
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text="Добавить", command=self.add_beer_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Удалить", command=self.delete_beer).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Показать этикетку", command=self.show_label).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Печать", command=self.print_label).pack(side=tk.LEFT, padx=2)

        # Правая панель - изображение этикетки
        right_frame = ttk.Frame(main_pane, relief=tk.SUNKEN, borderwidth=2)
        main_pane.add(right_frame, weight=2)

        self.image_label = ttk.Label(right_frame, text="Здесь будет этикетка", anchor=tk.CENTER)
        self.image_label.pack(fill=tk.BOTH, expand=True)

    def refresh_list(self, filter_text=None):
        """Обновляет список сортов в Listbox с учетом фильтра"""
        self.listbox.delete(0, tk.END)
        filtered = []
        if filter_text:
            ft = filter_text.lower()
            filtered = [b for b in self.beers if ft in b["Название"].lower() or ft in b["Тип"].lower()]
        else:
            filtered = self.beers

        for beer in filtered:
            self.listbox.insert(tk.END, beer["Название"])

        if filtered:
            self.listbox.selection_set(0)
            self.on_select()

    def search(self):
        """Поиск по введенному тексту"""
        text = self.filter_text.get().strip()
        self.refresh_list(text if text else None)

    def reset_search(self):
        """Сброс поиска и показ всех сортов"""
        self.filter_text.set("")
        self.refresh_list()

    def on_select(self, event=None):
        """Обработка выбора элемента в списке"""
        selection = self.listbox.curselection()
        if selection:
            index = selection[0]
            # Получаем название выбранного элемента
            name = self.listbox.get(index)
            # Ищем соответствующий словарь в self.beers
            for beer in self.beers:
                if beer["Название"] == name:
                    self.selected_beer = beer
                    break

    def add_beer_dialog(self):
        """Открывает диалог для добавления нового сорта"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Добавление сорта")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        fields = ["Название", "Тип", "Цена", "Приветствие"]
        entries = {}

        for i, field in enumerate(fields):
            ttk.Label(dialog, text=field + ":").grid(row=i, column=0, padx=5, pady=5, sticky=tk.W)
            entry = ttk.Entry(dialog, width=40)
            entry.grid(row=i, column=1, padx=5, pady=5)
            entries[field] = entry

        def save():
            new_beer = {}
            for field in fields:
                value = entries[field].get().strip()
                if not value:
                    messagebox.showwarning("Предупреждение", f"Поле '{field}' обязательно")
                    return
                new_beer[field] = value
            self.beers.append(new_beer)
            self.save_data()
            self.refresh_list()
            dialog.destroy()

        ttk.Button(dialog, text="Сохранить", command=save).grid(row=len(fields), column=0, columnspan=2, pady=10)

    def delete_beer(self):
        """Удаляет выбранный сорт"""
        if not self.selected_beer:
            messagebox.showinfo("Информация", "Выберите сорт для удаления")
            return

        confirm = messagebox.askyesno("Подтверждение", f"Удалить сорт '{self.selected_beer['Название']}'?")
        if confirm:
            self.beers.remove(self.selected_beer)
            self.save_data()
            self.selected_beer = None
            self.refresh_list()
            # Очищаем изображение
            self.image_label.config(image='', text='Этикетка удалена')

    def generate_label(self, beer):
        """Создает изображение этикетки для заданного сорта (аналогично боту)"""
        width, height = 580, 400
        img = Image.new("RGB", (width, height), "#11261A")
        draw = ImageDraw.Draw(img)

        try:
            font_logo = ImageFont.truetype("arialbd.ttf", 28)
            font_title = ImageFont.truetype("arialbd.ttf", 26)
            font_type = ImageFont.truetype("arial.ttf", 22)
            font_price = ImageFont.truetype("arialbd.ttf", 22)
            font_note = ImageFont.truetype("arial.ttf", 18)
        except:
            font_logo = font_title = font_type = font_price = font_note = ImageFont.load_default()

        def draw_left(text, y, font, padding=20):
            draw.text((padding, y), text, font=font, fill="white")

        draw_left("КультПива", 15, font_logo)
        draw_left(beer["Название"], 65, font_title)
        draw_left(beer["Тип"], 115, font_type)
        draw_left(f"Цена за 1л: {beer['Цена']} ₽", 165, font_price)
        draw_left(beer["Приветствие"], 215, font_note)

        return img

    def show_label(self):
        """Генерирует и отображает этикетку для выбранного сорта"""
        if not self.selected_beer:
            messagebox.showinfo("Информация", "Выберите сорт")
            return

        img = self.generate_label(self.selected_beer)
        # Конвертируем для Tkinter
        img_tk = ImageTk.PhotoImage(img)
        self.image_label.config(image=img_tk, text='')
        self.image_label.image = img_tk  # сохраняем ссылку

    def print_label(self):
        """Печатает этикетку для выбранного сорта"""
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


if __name__ == "__main__":
    root = tk.Tk()
    app = BeerLabelApp(root)
    root.mainloop()