section .data
    _str0: db "Hello World", 10, 0

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
    sub rsp, 0
    mov rdi, _str0
    call print
    mov rdi, 0
    call exit