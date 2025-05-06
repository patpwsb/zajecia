import sys
import os
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox

# Ustalamy ścieżki
if getattr(sys, 'frozen', False):
    # Uruchomione jako .exe
    base_dir = os.path.dirname(sys.executable)
else:
    # Uruchomione jako skrypt .py
    base_dir = os.path.dirname(os.path.realpath(__file__))
keys_dir = os.path.join(base_dir, 'keys')
config_path = os.path.join(base_dir, 'config')
keys_json_path = os.path.join(base_dir, 'keys.json')

# Sprawdzamy, czy foldery istnieją, jeśli nie, to je tworzymy
if not os.path.exists(keys_dir):
    os.makedirs(keys_dir)

if not os.path.exists(keys_json_path):
    with open(keys_json_path, 'w') as f:
        json.dump([], f)

# Funkcja generująca nowy klucz SSH
def generate_ssh_key(email, host, alias):
    # Sprawdzamy, czy wszystkie pola zostały wypełnione
    if not email or not host or not alias:
        QMessageBox.warning(window, "Błąd", "Wszystkie pola muszą być wypełnione!")
        return
    
    key_name = f"id_ed25519_{alias}"
    key_path = os.path.join(keys_dir, key_name)
    
    # Sprawdzamy, czy klucz już istnieje
    if os.path.exists(key_path):
        QMessageBox.critical(window, "Błąd", f"Klucz o nazwie {key_name} już istnieje!")
        return
    
    # Generowanie klucza
    try:
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-C", email, "-f", key_path, "-N", ""],
            check=True
        )
    except subprocess.CalledProcessError:
        QMessageBox.critical(window, "Błąd", "Nie udało się wygenerować klucza SSH.")
        return

    # Tworzymy config z poprawionym Hostem (usuwamy część po kropce w host)
    host_name = host.split('.')[0]  # Usuwamy część po kropce
    config_content = f"""
Host {host_name}-{alias}
    HostName {host}
    User git
    IdentityFile ~/.ssh/{key_name}
"""
    # Zmieniamy tutaj, aby plik config trafił do folderu keys, a nie config
    with open(os.path.join(keys_dir, f"{host_name}_{alias}_config"), 'w') as f:
        f.write(config_content.strip())

    # Dodanie metadanych do pliku keys.json
    key_metadata = {
        "key_name": key_name,
        "email": email,
        "hostname": host,
        "alias": alias,
        "key_path": key_path,
        "created": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    # Wczytanie i zapisanie danych do keys.json
    try:
        with open(keys_json_path, 'r') as f:
            keys_data = json.load(f)
    except json.JSONDecodeError:  # Obsługa pustego lub uszkodzonego pliku
        keys_data = []

    keys_data.append(key_metadata)
    
    with open(keys_json_path, 'w') as f:
        json.dump(keys_data, f, indent=4)

    # Aktualizacja tabeli
    update_table()


def copy_key_to_ssh():
    alias = alias_input.text().strip()
    if not alias:
        QMessageBox.warning(window, "Błąd", "Podaj alias do skopiowania.")
        return

    with open(keys_json_path, 'r') as f:
        keys_data = json.load(f)

    key_entry = next((k for k in keys_data if k['alias'] == alias), None)

    if not key_entry:
        QMessageBox.warning(window, "Błąd", f"Nie znaleziono aliasu {alias}.")
        return

    key_path = key_entry["key_path"]
    public_key_path = f"{key_path}.pub"
    destination = os.path.expanduser("~/.ssh/")

    if not os.path.exists(destination):
        os.makedirs(destination)

    try:
        shutil.copy(key_path, destination)
        shutil.copy(public_key_path, destination)
        
        # Kopiowanie configu z folderu 'keys' zamiast 'config'
        config_filename = f"{key_entry['hostname'].split('.')[0]}_{alias}_config"
        src_config_path = os.path.join(keys_dir, config_filename)  # Zmieniamy tutaj na 'keys_dir'
        if os.path.exists(src_config_path):
            shutil.copy(src_config_path, os.path.join(destination, "config"))  # Kopiujemy jako 'config'

        QMessageBox.information(window, "Sukces", f"Pliki skopiowane do {destination}")
    except Exception as e:
        QMessageBox.critical(window, "Błąd", f"Nie udało się skopiować: {e}")




# Funkcja usuwająca wszystko
def delete_all():
    reply = QMessageBox.question(window, 'Usuwanie', 'Czy na pewno chcesz usunąć wszystkie klucze i pliki konfiguracyjne?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    if reply == QMessageBox.StandardButton.Yes:
        # Usuwamy wszystkie klucze SSH z folderu keys
        for key in os.listdir(keys_dir):
            key_path = os.path.join(keys_dir, key)
            os.remove(key_path)

        # Usuwamy wszystkie pliki konfiguracyjne z folderu config
        for config_file in os.listdir(config_path):
            config_file_path = os.path.join(config_path, config_file)
            os.remove(config_file_path)

        # Usuwamy zawartość keys.json
        with open(keys_json_path, 'w') as f:
            json.dump([], f)

        # Aktualizujemy tabelę
        update_table()

        QMessageBox.information(window, "Sukces", "Wszystkie klucze i pliki konfiguracyjne zostały usunięte.")


# Funkcja usuwająca alias
def delete_alias():
    alias_to_delete = alias_input.text()  # Używamy tego samego pola 'alias_input'
    if not alias_to_delete:
        QMessageBox.warning(window, "Błąd", "Nie podano aliasu do usunięcia.")
        return
    
    with open(keys_json_path, 'r') as f:
        keys_data = json.load(f)
    
    # Filtrujemy klucze, usuwając te, które mają alias do usunięcia
    keys_data_to_delete = [key for key in keys_data if key['alias'] == alias_to_delete]

    if not keys_data_to_delete:
        QMessageBox.warning(window, "Błąd", f"Nie znaleziono aliasu {alias_to_delete}.")
        return
    
    # Usuwamy odpowiednie pliki klucza i plik konfiguracyjny
    for key in keys_data_to_delete:
        key_path = key['key_path']
        key_pub_path = f"{key_path}.pub"  # Ścieżka do klucza publicznego (z rozszerzeniem .pub)
        host_name = key['hostname'].split('.')[0]  # Usuwamy część po kropce w host
        config_file_path = os.path.join(keys_dir, f"{host_name}_{alias_to_delete}_config")  # Folder keys

        # Logowanie pełnej ścieżki do pliku konfiguracyjnego
        print(f"Ścieżka do pliku konfiguracyjnego: {config_file_path}")
        
        # Sprawdzamy, czy pliki istnieją i usuwamy je
        if os.path.exists(key_path):
            print(f"Usuwam klucz prywatny: {key_path}")  # Logowanie do konsoli
            os.remove(key_path)
        
        if os.path.exists(key_pub_path):
            print(f"Usuwam klucz publiczny: {key_pub_path}")  # Logowanie do konsoli
            os.remove(key_pub_path)
        
        if os.path.exists(config_file_path):
            print(f"Usuwam plik konfiguracyjny: {config_file_path}")  # Logowanie do konsoli
            os.remove(config_file_path)
        else:
            print(f"Plik konfiguracyjny nie istnieje: {config_file_path}")  # Logowanie do konsoli
        
    # Filtrujemy dane z pliku keys.json, usuwając wpisy dla tego aliasu
    keys_data = [key for key in keys_data if key['alias'] != alias_to_delete]

    # Zapisujemy zmienione dane z powrotem do pliku
    with open(keys_json_path, 'w') as f:
        json.dump(keys_data, f, indent=4)
    
    # Aktualizujemy tabelę po usunięciu aliasu
    update_table()

    # Wyświetlamy komunikat o sukcesie
    QMessageBox.information(window, "Sukces", f"Alias {alias_to_delete} został usunięty oraz wszystkie powiązane pliki.")



# Funkcja do wyświetlania zawartości plików konfiguracyjnych
def show_config():
    # Zmieniamy ścieżkę z folderu config na keys
    config_files = [os.path.join(keys_dir, f) for f in os.listdir(keys_dir) if f.endswith('_config')]  # Tylko pliki kończące się na _config
    
    if not config_files:
        QMessageBox.critical(window, "Błąd", "Brak plików konfiguracyjnych.")
        return

    full_config = ""
    for file in config_files:
        with open(file, 'r') as f:
            full_config += f.read() + "\n\n"

    # Wyświetlamy całą zawartość plików konfiguracyjnych
    QMessageBox.information(window, "Config SSH", full_config.strip())


# Funkcja pokazująca keys.json
def show_keys_json():
    with open(keys_json_path, 'r') as f:
        keys_data = json.load(f)

    if not keys_data:
        QMessageBox.critical(window, "Błąd", "Brak danych do wyświetlenia.")
        return

    json_content = json.dumps(keys_data, indent=4)
    QMessageBox.information(window, "keys.json", json_content)

# Funkcja aktualizująca tabelę
def update_table():
    with open(keys_json_path, 'r') as f:
        try:
            keys_data = json.load(f)
        except json.JSONDecodeError:
            keys_data = []  # W przypadku błędu parsowania pliku, traktujmy to jako pustą listę

    table.setRowCount(0)  # Usuwamy poprzednie wiersze w tabeli

    for key in keys_data:
        row_position = table.rowCount()
        table.insertRow(row_position)
        table.setItem(row_position, 0, QTableWidgetItem(key['key_name']))
        table.setItem(row_position, 1, QTableWidgetItem(key['hostname']))
        table.setItem(row_position, 2, QTableWidgetItem(key['alias']))
        table.setItem(row_position, 3, QTableWidgetItem(key['email']))

# Główna aplikacja GUI
app = QApplication(sys.argv)

# Ustawienie czarnego motywu
app.setStyleSheet("""
    QWidget {
        background-color: #2e2e2e;
        color: white;
        font-size: 14px;
    }
    QLineEdit, QPushButton, QTableWidget {
        background-color: #444444;
        border: 1px solid #888888;
        color: white;
    }
    QPushButton:hover {
        background-color: #555555;
    }
    QTableWidget {
        color: white;
        border: 1px solid #888888;
    }
    QHeaderView::section {
        background-color: #333333;
        color: white;
        font-weight: bold;
    }
""")

window = QWidget()
window.setWindowTitle("SSH Key Manager")
layout = QVBoxLayout()

# Wprowadzenie danych
form_layout = QVBoxLayout()

email_input = QLineEdit()
email_input.setPlaceholderText("Email")
form_layout.addWidget(email_input)

host_input = QLineEdit()
host_input.setPlaceholderText("Host")
form_layout.addWidget(host_input)

alias_input = QLineEdit()
alias_input.setPlaceholderText("Alias/Użytkownik")
form_layout.addWidget(alias_input)

layout.addLayout(form_layout)

# Przyciski
button_layout = QHBoxLayout()

generate_button = QPushButton("Generuj klucz")
generate_button.clicked.connect(lambda: generate_ssh_key(email_input.text(), host_input.text(), alias_input.text()))
button_layout.addWidget(generate_button)

copy_button = QPushButton("Kopiuj do ~/.ssh")
copy_button.clicked.connect(copy_key_to_ssh)
button_layout.addWidget(copy_button)

delete_all_button = QPushButton("Usuń wszystko")
delete_all_button.clicked.connect(delete_all)
button_layout.addWidget(delete_all_button)

delete_alias_button = QPushButton("Usuń alias")
delete_alias_button.clicked.connect(delete_alias)
button_layout.addWidget(delete_alias_button)

show_config_button = QPushButton("Pokaż config")
show_config_button.clicked.connect(show_config)
button_layout.addWidget(show_config_button)

show_keys_json_button = QPushButton("Pokaż keys.json")
show_keys_json_button.clicked.connect(show_keys_json)
button_layout.addWidget(show_keys_json_button)

layout.addLayout(button_layout)

# Tabela do wyświetlania kluczy
table = QTableWidget()
table.setColumnCount(4)
table.setHorizontalHeaderLabels(["Nazwa Klucza", "Host", "Alias", "Email"])
table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

layout.addWidget(table)

# Inicjalizacja widoku
window.setLayout(layout)
update_table()
window.show()

sys.exit(app.exec())
