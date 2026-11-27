; Временная библиотека Makakalang. Значения передаются как RAX=тип, RDX=данные.
; Типы: 0 — целое, 1 — строка, 2 — логическое, 3 — Ничего.

section .text

mk__write_bytes:
    test rdx, rdx
    jz .empty
    push rbp
    mov rbp, rsp
    sub rsp, 64
    mov [rbp-8], rcx
    mov [rbp-16], rdx
    mov qword [rbp-24], 0
    mov ecx, -11
    call GetStdHandle
    mov rcx, rax
    mov rdx, [rbp-8]
    mov r8, [rbp-16]
    lea r9, [rbp-24]
    mov qword [rsp+32], 0
    call WriteFile
    leave
.empty:
    ret

mk__print:
    push rbp
    mov rbp, rsp
    sub rsp, 64
    cmp rax, 0
    je .integer
    cmp rax, 1
    je .string
    cmp rax, 2
    je .boolean
    cmp rax, 3
    je .nothing
    jmp mk__err_type
.integer:
    call mk__print_integer
    leave
    ret
.string:
    mov rcx, rdx
    mov rdx, [rcx]
    add rcx, 8
    call mk__write_bytes
    leave
    ret
.boolean:
    test rdx, rdx
    jz .false
    lea rcx, [rel mk__text_true]
    mov edx, 12
    call mk__write_bytes
    leave
    ret
.false:
    lea rcx, [rel mk__text_false]
    mov edx, 8
    call mk__write_bytes
    leave
    ret
.nothing:
    lea rcx, [rel mk__text_nothing]
    mov edx, 12
    call mk__write_bytes
    leave
    ret

mk__print_integer:
    push rbp
    mov rbp, rsp
    sub rsp, 96
    mov rax, rdx
    lea r9, [rbp-16]
    mov r10, r9
    xor r11d, r11d
    test rax, rax
    jns .digits
    mov r11d, 1
    neg rax
.digits:
    mov rcx, 10
.next_digit:
    xor edx, edx
    div rcx
    add dl, '0'
    dec r10
    mov [r10], dl
    test rax, rax
    jnz .next_digit
    test r11d, r11d
    jz .write
    dec r10
    mov byte [r10], '-'
.write:
    mov rcx, r10
    mov rdx, r9
    sub rdx, r10
    call mk__write_bytes
    leave
    ret

mk__alloc:
    push rbp
    mov rbp, rsp
    sub rsp, 64
    mov [rbp-8], rcx
    call GetProcessHeap
    mov rcx, rax
    xor edx, edx
    mov r8, [rbp-8]
    call HeapAlloc
    test rax, rax
    jz mk__err_memory
    leave
    ret

; RCX — старый блок, RDX — новый размер. Возврат: RAX — новый блок.
mk__realloc:
    push rbp
    mov rbp, rsp
    sub rsp, 64
    mov [rbp-8], rcx
    mov [rbp-16], rdx
    call GetProcessHeap
    mov rcx, rax
    xor edx, edx
    mov r8, [rbp-8]
    mov r9, [rbp-16]
    call HeapReAlloc
    test rax, rax
    jz mk__err_memory
    leave
    ret

mk__input:
    push rbp
    mov rbp, rsp
    sub rsp, 96
    mov ecx, 4105
    call mk__alloc
    mov [rbp-8], rax
    mov ecx, -10
    call GetStdHandle
    mov [rbp-24], rax
    mov qword [rbp-32], 0
    mov qword [rbp-40], 4096
.read_next:
    mov rcx, [rbp-32]
    cmp rcx, [rbp-40]
    jb .space_ready
    mov rdx, [rbp-40]
    shl rdx, 1
    jc mk__err_memory
    mov [rbp-40], rdx
    add rdx, 9
    jc mk__err_memory
    mov rcx, [rbp-8]
    call mk__realloc
    mov [rbp-8], rax
.space_ready:
    mov rcx, [rbp-32]
    mov qword [rbp-16], 0
    mov rdx, [rbp-8]
    lea rdx, [rdx+rcx+8]
    mov rcx, [rbp-24]
    mov r8d, 1
    lea r9, [rbp-16]
    mov qword [rsp+32], 0
    call ReadFile
    test rax, rax
    jz .read_done
    cmp qword [rbp-16], 0
    je .read_done
    mov r10, [rbp-8]
    mov rcx, [rbp-32]
    mov al, [r10+rcx+8]
    cmp al, 10
    je .read_done
    inc rcx
    mov [rbp-32], rcx
    jmp .read_next
.read_done:
    mov r10, [rbp-8]
    mov rcx, [rbp-32]
.strip:
    test rcx, rcx
    jz .done
    mov al, [r10+rcx+7]
    cmp al, 10
    je .remove
    cmp al, 13
    jne .done
.remove:
    dec rcx
    jmp .strip
.done:
    mov [r10], rcx
    mov byte [r10+rcx+8], 0
    mov rdx, r10
    mov eax, 1
    leave
    ret

mk__to_integer:
    cmp rax, 1
    jne mk__err_number_string
    push rbp
    mov rbp, rsp
    sub rsp, 64
    mov dword [rbp-8], 0
    mov rcx, rdx
    add rcx, 8
    mov r8, rcx
    add r8, [rdx]
.skip_left:
    cmp rcx, r8
    jae .invalid
    mov al, [rcx]
    cmp al, ' '
    je .left_next
    cmp al, 9
    jne .sign
.left_next:
    inc rcx
    jmp .skip_left
.sign:
    mov r10, 0x7fffffffffffffff
    cmp al, '-'
    je .negative
    cmp al, '+'
    jne .begin
    inc rcx
    jmp .begin
.negative:
    mov dword [rbp-8], 1
    mov r10, 0x8000000000000000
    inc rcx
.begin:
    cmp rcx, r8
    jae .invalid
    xor eax, eax
.digit_loop:
    cmp rcx, r8
    jae .finish
    movzx r9d, byte [rcx]
    cmp r9b, ' '
    je .finish
    cmp r9b, 9
    je .finish
    sub r9d, '0'
    cmp r9d, 9
    ja .invalid
    mov r11, 10
    xor edx, edx
    mul r11
    test rdx, rdx
    jnz .invalid
    add rax, r9
    jc .invalid
    cmp rax, r10
    ja .invalid
    inc rcx
    jmp .digit_loop
.finish:
.skip_right:
    cmp rcx, r8
    jae .converted
    mov dl, [rcx]
    cmp dl, ' '
    je .right_next
    cmp dl, 9
    jne .invalid
.right_next:
    inc rcx
    jmp .skip_right
.converted:
    cmp dword [rbp-8], 0
    je .positive
    neg rax
.positive:
    mov rdx, rax
    xor eax, eax
    leave
    ret
.invalid:
    jmp mk__err_number

mk__add:
    cmp rax, rcx
    jne mk__err_add
    test rax, rax
    jz .integers
    cmp rax, 1
    je .strings
    jmp mk__err_add
.integers:
    add rdx, r8
    jo mk__err_overflow
    xor eax, eax
    ret
.strings:
    push rbp
    mov rbp, rsp
    sub rsp, 96
    mov [rbp-8], rdx
    mov [rbp-16], r8
    mov [rbp-40], rsi
    mov [rbp-48], rdi
    mov r9, [rdx]
    mov r10, [r8]
    mov [rbp-24], r9
    mov [rbp-32], r10
    mov rcx, r9
    add rcx, r10
    jc mk__err_memory
    add rcx, 9
    jc mk__err_memory
    call mk__alloc
    mov r11, rax
    mov rcx, [rbp-24]
    add rcx, [rbp-32]
    mov [r11], rcx
    lea rdi, [r11+8]
    mov rsi, [rbp-8]
    add rsi, 8
    mov rcx, [rbp-24]
    cld
    rep movsb
    mov rsi, [rbp-16]
    add rsi, 8
    mov rcx, [rbp-32]
    rep movsb
    mov byte [rdi], 0
    mov rsi, [rbp-40]
    mov rdi, [rbp-48]
    mov rdx, r11
    mov eax, 1
    leave
    ret

mk__sub:
    call mk__require_integers
    sub rdx, r8
    jo mk__err_overflow
    xor eax, eax
    ret

mk__mul:
    call mk__require_integers
    mov rax, rdx
    imul rax, r8
    jo mk__err_overflow
    mov rdx, rax
    xor eax, eax
    ret

mk__div:
    call mk__require_integers
    test r8, r8
    jz mk__err_zero
    mov rax, 0x8000000000000000
    cmp rdx, rax
    jne .divide
    cmp r8, -1
    je mk__err_overflow
.divide:
    mov rax, rdx
    cqo
    idiv r8
    mov rdx, rax
    xor eax, eax
    ret

mk__mod:
    call mk__require_integers
    test r8, r8
    jz mk__err_zero
    mov rax, 0x8000000000000000
    cmp rdx, rax
    jne .divide
    cmp r8, -1
    je .zero
.divide:
    mov rax, rdx
    cqo
    idiv r8
    xor eax, eax
    ret
.zero:
    xor edx, edx
    xor eax, eax
    ret

mk__require_integers:
    test rax, rax
    jnz mk__err_integers
    test rcx, rcx
    jnz mk__err_integers
    ret

mk__negate:
    test rax, rax
    jnz mk__err_integer
    neg rdx
    jo mk__err_overflow
    xor eax, eax
    ret

mk__positive:
    test rax, rax
    jnz mk__err_integer
    ret

mk__truthy:
    test rax, rax
    jz .integer
    cmp rax, 1
    je .string
    cmp rax, 2
    je .boolean
    cmp rax, 3
    je .false
    jmp .false
.integer:
    test rdx, rdx
    setnz al
    movzx eax, al
    ret
.string:
    cmp qword [rdx], 0
    setne al
    movzx eax, al
    ret
.boolean:
    mov rax, rdx
    ret
.false:
    xor eax, eax
    ret

mk__equal:
    cmp rax, rcx
    jne .different
    cmp rax, 1
    je .strings
    cmp rax, 3
    je .same
    cmp rdx, r8
    sete al
    movzx eax, al
    jmp .boolean
.strings:
    push rbp
    mov rbp, rsp
    sub rsp, 32
    call mk__string_compare
    test eax, eax
    sete al
    movzx eax, al
    leave
    jmp .boolean
.same:
    mov eax, 1
    jmp .boolean
.different:
    xor eax, eax
.boolean:
    mov edx, eax
    mov eax, 2
    ret

mk__compare:
    push rbp
    mov rbp, rsp
    sub rsp, 64
    mov [rbp-8], r9
    cmp rax, rcx
    jne mk__err_compare
    test rax, rax
    jz .integers
    cmp rax, 1
    je .strings
    jmp mk__err_compare
.integers:
    cmp rdx, r8
    jl .less
    jg .greater
    xor eax, eax
    jmp .result
.strings:
    call mk__string_compare
    jmp .result
.less:
    mov eax, -1
    jmp .result
.greater:
    mov eax, 1
.result:
    mov r9, [rbp-8]
    cmp r9, 0
    je .less_test
    cmp r9, 1
    je .less_equal_test
    cmp r9, 2
    je .greater_test
    cmp eax, 0
    setge al
    movzx eax, al
    jmp .boolean
.less_test:
    cmp eax, 0
    setl al
    movzx eax, al
    jmp .boolean
.less_equal_test:
    cmp eax, 0
    setle al
    movzx eax, al
    jmp .boolean
.greater_test:
    cmp eax, 0
    setg al
    movzx eax, al
.boolean:
    mov edx, eax
    mov eax, 2
    leave
    ret

; RDX — левая строка, R8 — правая. Возврат: EAX < 0, 0 или > 0.
mk__string_compare:
    mov r9, [rdx]
    mov r10, [r8]
    mov r11, r9
    cmp r11, r10
    jbe .length_ready
    mov r11, r10
.length_ready:
    add rdx, 8
    add r8, 8
    xor ecx, ecx
.loop:
    cmp rcx, r11
    jae .by_length
    mov al, [rdx+rcx]
    cmp al, [r8+rcx]
    jb .less
    ja .greater
    inc rcx
    jmp .loop
.by_length:
    cmp r9, r10
    jb .less
    ja .greater
    xor eax, eax
    ret
.less:
    mov eax, -1
    ret
.greater:
    mov eax, 1
    ret

mk__fatal:
    ; Сюда можно попасть командой jmp из любого места, поэтому выравниваем
    ; стек самостоятельно. Функция никогда не возвращается.
    and rsp, -16
    sub rsp, 96
    mov [rsp+64], rcx
    mov [rsp+72], rdx
    lea rcx, [rel mk__error_prefix]
    mov edx, mk__error_prefix_len
    call mk__write_bytes
    mov rcx, [rsp+64]
    mov rdx, [rsp+72]
    call mk__write_bytes
    lea rcx, [rel mk__newline]
    mov edx, 2
    call mk__write_bytes
    mov ecx, 1
    call ExitProcess

mk__err_type:
    lea rcx, [rel mk__msg_type]
    mov edx, mk__msg_type_len
    jmp mk__fatal
mk__err_add:
    lea rcx, [rel mk__msg_add]
    mov edx, mk__msg_add_len
    jmp mk__fatal
mk__err_integers:
    lea rcx, [rel mk__msg_integers]
    mov edx, mk__msg_integers_len
    jmp mk__fatal
mk__err_integer:
    lea rcx, [rel mk__msg_integer]
    mov edx, mk__msg_integer_len
    jmp mk__fatal
mk__err_zero:
    lea rcx, [rel mk__msg_zero]
    mov edx, mk__msg_zero_len
    jmp mk__fatal
mk__err_overflow:
    lea rcx, [rel mk__msg_overflow]
    mov edx, mk__msg_overflow_len
    jmp mk__fatal
mk__err_number_string:
    lea rcx, [rel mk__msg_number_string]
    mov edx, mk__msg_number_string_len
    jmp mk__fatal
mk__err_number:
    lea rcx, [rel mk__msg_number]
    mov edx, mk__msg_number_len
    jmp mk__fatal
mk__err_memory:
    lea rcx, [rel mk__msg_memory]
    mov edx, mk__msg_memory_len
    jmp mk__fatal
mk__err_compare:
    lea rcx, [rel mk__msg_compare]
    mov edx, mk__msg_compare_len
    jmp mk__fatal

section .data
mk__text_true: db "Истина"
mk__text_false: db "Ложь"
mk__text_nothing: db "Ничего"
mk__newline: db 13, 10
mk__error_prefix: db "Ошибка выполнения: "
mk__error_prefix_len equ $ - mk__error_prefix
mk__msg_type: db "неизвестный тип значения"
mk__msg_type_len equ $ - mk__msg_type
mk__msg_add: db "оператор '+' требует два целых числа или две строки"
mk__msg_add_len equ $ - mk__msg_add
mk__msg_integers: db "арифметический оператор требует два целых числа"
mk__msg_integers_len equ $ - mk__msg_integers
mk__msg_integer: db "унарный оператор требует целое число"
mk__msg_integer_len equ $ - mk__msg_integer
mk__msg_zero: db "деление на ноль"
mk__msg_zero_len equ $ - mk__msg_zero
mk__msg_overflow: db "переполнение 64-битного целого числа"
mk__msg_overflow_len equ $ - mk__msg_overflow
mk__msg_number_string: db "функция 'число' ожидает строку"
mk__msg_number_string_len equ $ - mk__msg_number_string
mk__msg_number: db "не удалось преобразовать строку в целое число"
mk__msg_number_len equ $ - mk__msg_number
mk__msg_memory: db "недостаточно памяти или превышен размер строки"
mk__msg_memory_len equ $ - mk__msg_memory
mk__msg_compare: db "упорядочивающее сравнение требует два целых числа или две строки"
mk__msg_compare_len equ $ - mk__msg_compare
