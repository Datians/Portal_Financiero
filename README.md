# 💰 Portal Financiero con Autenticación Multifactor (MFA)

## 📌 Descripción general

El **Portal Financiero** es una aplicación web desarrollada en **Python utilizando Flask**, orientada a la gestión financiera personal y diseñada con un enfoque fuerte en **seguridad**.  
El sistema implementa **Autenticación Multifactor (MFA)** mediante el uso de **contraseña + código OTP (One-Time Password)** enviado al correo electrónico del usuario.

El proyecto simula el comportamiento de un portal financiero real, donde no solo el acceso al sistema está protegido, sino también las **operaciones críticas**, tales como transferencias y creación de cuentas bancarias, evitando accesos indebidos o suplantación de identidad.

Este proyecto fue desarrollado con **fines académicos**, cumpliendo con los requisitos del **Segundo Entregable: Prototipo Funcional y Documentación Final**.

---

## 🎯 Objetivos del proyecto

- Implementar un sistema de **autenticación multifactor real (MFA)**.
- Proteger el inicio de sesión mediante **verificación por correo electrónico**.
- Añadir una **capa de seguridad adicional** para operaciones críticas:
  - Creación de cuentas bancarias.
  - Transferencias internas.
  - Transferencias a otros usuarios.
- Aplicar buenas prácticas de seguridad en aplicaciones web.
- Desplegar un prototipo funcional accesible desde la nube.

---

## 🏗️ Arquitectura del sistema

El sistema sigue una arquitectura **cliente-servidor**:

- **Frontend**
  - Plantillas HTML renderizadas con **Jinja2**.
  - Estilos CSS para la interfaz de usuario.

- **Backend**
  - Framework **Flask** para la lógica del sistema.
  - **SQLAlchemy** como ORM.
  - Gestión de sesiones y autenticación.

- **Base de datos**
  - **SQLite**, utilizada para persistencia de datos en entorno académico.

- **Seguridad**
  - Contraseñas almacenadas con hash.
  - OTP de un solo uso con tiempo de expiración.
  - Validación de sesión en rutas protegidas.
  - MFA aplicado a operaciones críticas.

---

## 🔐 Flujo de autenticación (MFA)

### 1️⃣ Registro de usuario
- El usuario se registra con correo electrónico y contraseña.
- La contraseña se almacena de forma cifrada.
- El usuario debe verificar su correo antes de acceder.

### 2️⃣ Inicio de sesión (Primer factor)
- El usuario ingresa correo y contraseña.
- El sistema valida las credenciales.

### 3️⃣ Envío de OTP (Segundo factor)
- Se genera un código OTP único.
- El código se envía al correo electrónico del usuario.
- El OTP tiene tiempo limitado de validez.

### 4️⃣ Validación del OTP
- El usuario ingresa el código recibido.
- Si el código es correcto y no ha expirado, se concede acceso al sistema.

---

## 🔒 MFA en operaciones críticas

Además del inicio de sesión, el sistema solicita **verificación OTP adicional** cuando el usuario intenta realizar acciones sensibles, tales como:

- 🏦 Creación de cuentas bancarias.
- 💸 Transferencias internas entre cuentas.
- 🔁 Transferencias a otros usuarios.

Esto garantiza que incluso si una sesión es comprometida, las operaciones críticas no puedan ejecutarse sin una segunda verificación.

---

## 📂 Estructura del proyecto

Portal_Financiero/
│
├── app/
│ ├── init.py # Inicialización de la aplicación Flask
│ ├── auth/ # Autenticación y MFA
│ ├── finance/ # Lógica financiera
│ ├── models.py # Modelos de base de datos
│ ├── templates/ # Plantillas HTML
│ └── static/ # Archivos CSS
│
├── instance/ # Base de datos SQLite
├── init_db.py # Inicialización de la base de datos
├── run.py # Punto de entrada del sistema
├── requirements.txt # Dependencias
└── README.md # Documentación



---

## ⚙️ Tecnologías utilizadas

- **Python 3**
- **Flask**
- **Flask-SQLAlchemy**
- **Jinja2**
- **Gunicorn**
- **SQLite**
- **Servicio de correo (Resend / SMTP)**
- **HTML y CSS**

---

## 🧪 Pruebas realizadas

- Inicio de sesión con credenciales incorrectas.
- OTP incorrecto o expirado.
- Reutilización de OTP.
- Acceso a rutas protegidas sin sesión.
- Intentos de transferencia sin validación OTP.

✔️ En todos los casos, el sistema bloqueó correctamente el acceso u operación.

---

## 🚀 Instalación y ejecución local

### 1️⃣ Clonar el repositorio

git clone https://github.com/Datians/Portal_Financiero.git
cd Portal_Financiero

### 2️⃣ Crear entorno virtual
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

3️⃣ Instalar dependencias
pip install -r requirements.txt

4️⃣ Configurar variables de entorno

Crear un archivo .env con:

SECRET_KEY=clave_secreta_segura
DATABASE_URL=sqlite:///portal_financiero.db
RESEND_API_KEY=tu_api_key
OTP_EXP_MINUTES=5

5️⃣ Inicializar la base de datos
python init_db.py

6️⃣ Ejecutar la aplicación
python run.py


Acceder desde el navegador a:

http://127.0.0.1:5000


📄 Autor

David Andrés Cuadrado
Proyecto académico – Seguridad Informática
Portal Financiero con MFA
