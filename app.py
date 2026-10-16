from flask import Flask, request, jsonify, render_template
import ctypes
import subprocess
import os
import time

app = Flask(__name__)

EMU8086_PATH = r"C:\emu8086\emu8086.exe"
SHORT_FILE_NAME = "res.txt"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

POSSIBLE_PATHS = [
    os.path.join(BASE_DIR, SHORT_FILE_NAME),
    os.path.join(BASE_DIR, "MyBuild", SHORT_FILE_NAME),
    r"C:\emu8086\MyBuild\res.txt",
    r"C:\emu8086\vdrive\c\res.txt",
    r"C:\emu8086\res.txt"
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calcular', methods=['POST'])
def calcular():
    data = request.json or {}

    try:
        num1 = float(data.get('num1', 0))
        num2 = float(data.get('num2', 0))
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Entrada numérica no válida"}), 400

    # Escalamiento x100 para punto fijo de 16 bits en ensamblador
    num1_scaled = int(round(num1 * 100))
    num2_scaled = int(round(num2 * 100))

    if abs(num1_scaled) > 32767 or abs(num2_scaled) > 32767:
        return jsonify({
            "status": "error_matematico",
            "message": "Los números superan el rango de 16 bits del 8086 (-327.67 a 327.67)."
        }), 400

    operacion = data.get('operacion', 'suma')

    limpiar_archivos_previos()
    generar_codigo_ensamblador(num1_scaled, num2_scaled, operacion)
    ruta_asm = os.path.abspath("operacion_generada.asm")

    if os.path.exists(EMU8086_PATH):
        try:
            subprocess.Popen([EMU8086_PATH, ruta_asm])
        except Exception as e:
            return jsonify({"status": "error_ensamblador", "message": f"No se pudo iniciar emu8086: {e}"})
    else:
        return jsonify({"status": "error_ensamblador", "message": f"No se encontró emu8086 en '{EMU8086_PATH}'"})

    timeout = 40
    start_time = time.time()
    contenido = None
    archivo_encontrado = None

    while time.time() - start_time < timeout:
        for path in POSSIBLE_PATHS:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        data_read = f.read().strip()
                    if data_read:
                        contenido = data_read
                        archivo_encontrado = path
                        break
                except Exception:
                    pass
        if contenido:
            break
        time.sleep(0.1)

    if archivo_encontrado and os.path.exists(archivo_encontrado):
        try:
            os.remove(archivo_encontrado)
        except Exception:
            pass

    if contenido is None:
        return jsonify({
            "status": "error_ensamblador",
            "message": "Tiempo de espera agotado sin respuesta del ensamblador."
        })

    if "CANCELADO" in contenido:
        return jsonify({
            "status": "no_enviado",
            "message": "Operación cancelada desde el emulador 8086."
        })

    if "ERROR_DIV_ZERO" in contenido:
        return jsonify({
            "status": "error_matematico",
            "message": "Error en Ensamblador: División por cero no permitida."
        })

    try:
        resultado_float = float(contenido)
        
        # 1. Decimal exacto
        if abs(resultado_float - round(resultado_float)) < 1e-5:
            dec_exacto = str(int(round(resultado_float)))
        else:
            dec_exacto = f"{resultado_float:.2f}".rstrip('0').rstrip('.')

        # 2. Hexadecimal y Binario exactos correspondientes al resultado
        hex_exacto, bin_exacto = float_to_hex_bin(resultado_float)

        return jsonify({
            "status": "ok",
            "dec": dec_exacto,
            "hex": hex_exacto,
            "bin": bin_exacto
        })
    except ValueError:
        return jsonify({
            "status": "error_ensamblador",
            "message": "Respuesta no válida del ensamblador."
        })


def float_to_hex_bin(val):
    """Convierte un valor numérico a su representación Hexadecimal y Binaria exacta."""
    # Si es un número entero
    if abs(val - round(val)) < 1e-5:
        int_val = int(round(val)) & 0xFFFF
        return f"{int_val:X}", f"{int_val:b}"
    
    # Si es un número decimal (punto flotante)
    sign = "-" if val < 0 else ""
    abs_val = abs(val)
    int_part = int(abs_val)
    frac_part = abs_val - int_part
    
    hex_int = f"{int_part:X}"
    bin_int = f"{int_part:b}"
    
    # Fracción Hexadecimal (hasta 2 dígitos)
    hex_frac = ""
    temp_frac = frac_part
    for _ in range(2):
        temp_frac *= 16
        digit = int(temp_frac)
        hex_frac += f"{digit:X}"
        temp_frac -= digit
    hex_frac = hex_frac.rstrip('0')
    
    # Fracción Binaria (hasta 4 dígitos)
    bin_frac = ""
    temp_frac = frac_part
    for _ in range(4):
        temp_frac *= 2
        digit = int(temp_frac)
        bin_frac += str(digit)
        temp_frac -= digit
    bin_frac = bin_frac.rstrip('0')
    
    hex_str = f"{sign}{hex_int}.{hex_frac}" if hex_frac else f"{sign}{hex_int}"
    bin_str = f"{sign}{bin_int}.{bin_frac}" if bin_frac else f"{sign}{bin_int}"
    
    return hex_str, bin_str


def limpiar_archivos_previos():
    for path in POSSIBLE_PATHS:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass


def generar_codigo_ensamblador(n1_scaled, n2_scaled, op):
    if op == 'suma':
        instruccion = "add ax, bx"
    elif op == 'resta':
        instruccion = "sub ax, bx"
    elif op == 'multiplicacion':
        instruccion = """
    imul bx
    mov cx, 100
    idiv cx"""
    elif op == 'division':
        instruccion = """
    cmp bx, 0
    je div_por_cero
    mov cx, 100
    imul cx
    idiv bx
    jmp operacion_lista
div_por_cero:
    lea dx, StrDivZero
    mov cx, 14
    call crear_y_escribir_archivo
    jmp fin_programa
operacion_lista:"""
    else:
        instruccion = "nop"

    codigo_asm = f"""
#make_exe#

.model small
.stack 200h

.data
    Num1 dw {n1_scaled}
    Num2 dw {n2_scaled}
    Resultado dw 0

    FileName db "res.txt", 0
    FileHandle dw 0

    MsgPrompt db 13, 10, "Calculo realizado en 8086.", 13, 10
              db "Desea enviar el resultado a la interfaz web? (S/N): $"
    MsgEnviado db 13, 10, "Resultado enviado exitosamente.$"
    MsgCancelado db 13, 10, "Envio cancelado por el usuario.$"

    StrCancel db "CANCELADO"
    StrDivZero db "ERROR_DIV_ZERO"
    BufferDec db 16 dup(0)
    BufLen dw 0

.code
inicio:
    mov ax, @data
    mov ds, ax

    mov ax, Num1
    mov bx, Num2
    
    {instruccion}

    mov Resultado, ax

    mov ah, 9
    lea dx, MsgPrompt
    int 21h

    mov ah, 1
    int 21h

    cmp al, 'S'
    je enviar_web
    cmp al, 's'
    je enviar_web

    mov ah, 9
    lea dx, MsgCancelado
    int 21h

    lea dx, StrCancel
    mov cx, 9
    call crear_y_escribir_archivo
    jmp fin_programa

enviar_web:
    mov ah, 9
    lea dx, MsgEnviado
    int 21h

    call scaled_to_string

    lea dx, BufferDec
    mov cx, BufLen
    call crear_y_escribir_archivo

fin_programa:
    mov ah, 4ch
    int 21h

crear_y_escribir_archivo proc
    push ax
    push bx
    push dx
    push cx

    mov bx, dx

    mov ah, 3Ch
    mov cx, 0
    lea dx, FileName
    int 21h
    mov FileHandle, ax

    mov ah, 40h
    mov bx, FileHandle
    pop cx
    pop dx
    int 21h

    mov ah, 3Eh
    mov bx, FileHandle
    int 21h

    pop bx
    pop ax
    ret
crear_y_escribir_archivo endp

scaled_to_string proc
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es

    mov cx, ds
    mov es, cx
    lea di, BufferDec
    mov cx, 16
    mov al, 0
    cld
    rep stosb

    lea si, BufferDec
    mov BufLen, 0

    mov ax, Resultado

    cmp ax, 0
    jge es_positivo
    neg ax
    mov byte ptr [si], '-'
    inc si
    inc BufLen

es_positivo:
    mov dx, 0
    mov bx, 100
    div bx

    push dx

    mov cx, 0
    mov bx, 10
loop_entero_div:
    mov dx, 0
    div bx
    push dx
    inc cx
    cmp ax, 0
    jne loop_entero_div

loop_entero_pop:
    pop dx
    add dl, '0'
    mov [si], dl
    inc si
    inc BufLen
    loop loop_entero_pop

    mov byte ptr [si], '.'
    inc si
    inc BufLen

    pop ax
    mov bl, 10
    div bl

    add al, '0'
    mov [si], al
    inc si
    inc BufLen

    add ah, '0'
    mov [si], ah
    inc si
    inc BufLen

    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
scaled_to_string endp

end inicio
"""

    with open("operacion_generada.asm", "w", encoding="utf-8") as file:
        file.write(codigo_asm)

if __name__ == '__main__':
    app.run(debug=True, port=5000)