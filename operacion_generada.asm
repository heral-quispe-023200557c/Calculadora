
#make_exe#

.model small
.stack 200h

.data
    Num1 dw 1250
    Num2 dw -250
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
    
    add ax, bx

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
