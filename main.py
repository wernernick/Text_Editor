"""Einstiegspunkt des Text Editors."""
import customtkinter as ctk


def main() -> None:
    ctk.set_appearance_mode("dark")
    app = ctk.CTk()
    app.title("Text Editor")
    app.geometry("1100x700")
    app.mainloop()


if __name__ == "__main__":
    main()
