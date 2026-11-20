import tkinter as tk
from tkinter import messagebox

class Calculator:
    def __init__(self, root):
        self.root = root
        self.root.title("ماشین‌حساب")
        self.root.geometry("300x400")
        self.root.resizable(False, False)

        # وضعیت محاسبات
        self.first_operand = None
        self.operator = None
        self.current_input = ""
        self.waiting_for_second_operand = False
        self.display_var = tk.StringVar()
        self.display_var.set("0")

        # نمایشگر
        display_frame = tk.Frame(root)
        display_frame.pack(pady=10)

        self.display = tk.Entry(
            display_frame,
            textvariable=self.display_var,
            font=("Arial", 20),
            justify="right",
            state="readonly",
            bd=5,
            relief="sunken"
        )
        self.display.pack()

        # دکمه‌ها
        button_frame = tk.Frame(root)
        button_frame.pack()

        buttons = [
            'C', '±', '%', '÷',
            '7', '8', '9', '×',
            '4', '5', '6', '-',
            '1', '2', '3', '+',
            '0', '.', '='
        ]

        row = 0
        col = 0
        for button in buttons:
            if button == '0':
                btn = tk.Button(button_frame, text=button, width=8, height=2, font=("Arial", 14))
                btn.grid(row=row, column=col, columnspan=2, sticky="nsew")
                col += 2
            elif button == '=':
                btn = tk.Button(button_frame, text=button, width=8, height=2, font=("Arial", 14), bg="#FF9500")
                btn.grid(row=row, column=col, sticky="nsew")
                col += 1
            else:
                btn = tk.Button(button_frame, text=button, width=8, height=2, font=("Arial", 14))
                btn.grid(row=row, column=col, sticky="nsew")
                col += 1

            if button == '=':
                btn.config(command=self.calculate)
            elif button in ['C', '±', '%']:
                btn.config(command=lambda b=button: self.clear(b))
            elif button in ['+', '-', '×', '÷']:
                btn.config(command=lambda b=button: self.set_operator(b))
            elif button == '.':
                btn.config(command=self.add_decimal)
            else:
                btn.config(command=lambda b=button: self.input_number(b))

            if col > 3:
                row += 1
                col = 0

        # اتصال کلیدهای صفحه‌کلید
        root.bind('<Key>', self.key_press)
        root.focus_set()

    def input_number(self, num):
        if self.waiting_for_second_operand:
            self.current_input = ""
            self.waiting_for_second_operand = False

        if self.current_input == "0":
            self.current_input = str(num)
        else:
            self.current_input += str(num)

        self.update_display()

    def add_decimal(self):
        if self.waiting_for_second_operand:
            self.current_input = ""
            self.waiting_for_second_operand = False

        if '.' not in self.current_input:
            if self.current_input == "":
                self.current_input = "0."
            else:
                self.current_input += "."
            self.update_display()

    def set_operator(self, op):
        if self.first_operand is None:
            self.first_operand = float(self.current_input)
        elif not self.waiting_for_second_operand:
            self.calculate()

        self.operator = op
        self.waiting_for_second_operand = True

    def calculate(self):
        if self.operator is None or self.first_operand is None:
            return

        try:
            second_operand = float(self.current_input)

            if self.operator == '+':
                result = self.first_operand + second_operand
            elif self.operator == '-':
                result = self.first_operand - second_operand
            elif self.operator == '×':
                result = self.first_operand * second_operand
            elif self.operator == '÷':
                if second_operand == 0:
                    messagebox.showerror("خطا", "تقسیم بر صفر ممکن نیست!")
                    self.clear('C')
                    return
                result = self.first_operand / second_operand

            # حفظ نتیجه برای محاسبات بعدی
            self.first_operand = result
            self.current_input = str(result)
            self.operator = None
            self.waiting_for_second_operand = True

            self.update_display()

        except Exception:
            messagebox.showerror("خطا", "محاسبه اشتباه است!")
            self.clear('C')

    def clear(self, action):
        if action == 'C':
            self.first_operand = None
            self.operator = None
            self.current_input = ""
            self.waiting_for_second_operand = False
        elif action == '±':
            if self.current_input:
                if self.current_input.startswith('-'):
                    self.current_input = self.current_input[1:]
                else:
                    self.current_input = '-' + self.current_input
                self.update_display()
        elif action == '%':
            if self.current_input:
                value = float(self.current_input)
                self.current_input = str(value / 100)
                self.update_display()

    def update_display(self):
        if self.current_input == "":
            self.display_var.set("0")
        else:
            # حذف صفرهای اضافی در انتهای اعشار
            try:
                num = float(self.current_input)
                if num.is_integer():
                    self.display_var.set(str(int(num)))
                else:
                    self.display_var.set(str(num))
            except ValueError:
                self.display_var.set(self.current_input)

    def key_press(self, event):
        key = event.char
        if key.isdigit() or key == '.':
            self.input_number(key)
        elif key in ['+', '-', '*', '/']:
            op_map = {'+': '+', '-': '-', '*': '×', '/': '÷'}
            self.set_operator(op_map[key])
        elif key == '\r':
            self.calculate()
        elif key == '\x08':
            self.clear('C')
        elif key == '%':
            self.clear('%')

if __name__ == "__main__":
    root = tk.Tk()
    calc = Calculator(root)
    root.mainloop()
