section .data
    _str0: db "Opening: ", 0
    _str1: db 10, 0
    _str2: db "Please provide an input file", 10, 0

section .bss
    file: resb 1024

section .text

global strlen
strlen:
    push rbp
    mov rbp, rsp
    sub rsp, 24
    mov [rbp - 8], rdi
    mov rax, 0
    mov [rbp - 16], rax
    mov rax, 0
    mov [rbp - 24], rax
.for_start_0:
    mov rdi, [rbp - 8]
    mov rax, [rbp - 24]
    add rdi, rax
    movzx rax, byte [rdi]
    mov rbx, 0
    cmp rax, rbx
    je .for_end_0
    mov rax, [rbp - 16]
    mov rbx, 1
    add rax, rbx
    mov [rbp - 16], rax
    mov rax, [rbp - 24]
    mov rbx, 1
    add rax, rbx
    mov [rbp - 24], rax
    jmp .for_start_0
.for_end_0:
    mov rax, [rbp - 16]
    mov rsp, rbp
    pop rbp
    ret
global print
print:
    push rbp
    mov rbp, rsp
    sub rsp, 16
    mov [rbp - 8], rdi
    mov rdi, [rbp - 8]
    call strlen
    mov [rbp - 16], rax
    mov rax, 1
    mov rdi, 1
    mov rsi, [rbp - 8]
    mov rdx, [rbp - 16]
    syscall
    mov rax, 0
    mov rsp, rbp
    pop rbp
    ret
global eprint
eprint:
    push rbp
    mov rbp, rsp
    sub rsp, 16
    mov [rbp - 8], rdi
    mov rdi, [rbp - 8]
    call strlen
    mov [rbp - 16], rax
    mov rax, 1
    mov rdi, 2
    mov rsi, [rbp - 8]
    mov rdx, [rbp - 16]
    syscall
    mov rax, 0
    mov rsp, rbp
    pop rbp
    ret
global exit
exit:
    push rbp
    mov rbp, rsp
    sub rsp, 8
    mov [rbp - 8], rdi
    mov rax, 60
    mov rdi, [rbp - 8]
    syscall
global _start
_start:
    push rbp
    mov rbp, rsp
    sub rsp, 16
    mov rax, 0
    mov [rbp - 8], rax
    mov rax, 0
    mov [rbp - 16], rax
    mov rax, [rbp + 8]
    mov [rbp - 8], rax
    lea rax, [rbp + 16]
    mov [rbp - 16], rax
    mov rdi, [rbp - 8]
    mov rsi, [rbp - 16]
    call main
    push rax
    pop rdi
    call exit
global open
open:
    push rbp
    mov rbp, rsp
    sub rsp, 24
    mov [rbp - 8], rdi
    mov [rbp - 16], rsi
    mov rax, 0
    mov [rbp - 24], rax
    mov rax, 2
    mov rdi, [rbp - 8]
    mov rsi, [rbp - 16]
    syscall
    mov [rbp - 24], rax
    mov rax, [rbp - 24]
    mov rsp, rbp
    pop rbp
    ret
global close
close:
    push rbp
    mov rbp, rsp
    sub rsp, 8
    mov [rbp - 8], rdi
    mov rax, 3
    mov rdi, [rbp - 8]
    syscall
    mov rax, 0
    mov rsp, rbp
    pop rbp
    ret
global read
read:
    push rbp
    mov rbp, rsp
    sub rsp, 32
    mov [rbp - 8], rdi
    mov [rbp - 16], rsi
    mov [rbp - 24], rdx
    mov rax, 0
    mov [rbp - 32], rax
    mov rax, 0
    mov rdi, [rbp - 8]
    mov rsi, [rbp - 16]
    mov rdx, [rbp - 24]
    syscall
    mov [rbp - 32], rax
    mov rax, [rbp - 32]
    mov rsp, rbp
    pop rbp
    ret
global main
main:
    push rbp
    mov rbp, rsp
    sub rsp, 24
    mov [rbp - 8], rdi
    mov [rbp - 16], rsi
    mov rax, [rbp - 8]
    mov rbx, 1
    cmp rax, rbx
    jle .if_else_1
    mov rdi, _str0
    call print
    mov rdi, [rbp - 16]
    mov rdi, [rdi + 8]
    call print
    mov rdi, _str1
    call print
    mov rdi, [rbp - 16]
    mov rdi, [rdi + 8]
    mov rsi, 0
    call open
    mov [rbp - 24], rax
    mov rdi, [rbp - 24]
    mov rsi, file
    mov rdx, 1024
    call read
    mov rdi, [rbp - 24]
    call close
    mov rdi, file
    call print
    mov rax, 0
    mov rsp, rbp
    pop rbp
    ret
    jmp .if_end_1
.if_else_1:
    mov rdi, _str2
    call eprint
    mov rax, 1
    mov rsp, rbp
    pop rbp
    ret
.if_end_1: