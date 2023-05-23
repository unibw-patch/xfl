import context
from classes.symbol import Symbol
from classes.basicblocksequence import LiveVariableAnalysis
from classes.symbolic_execution_engine import SymbolicExecutionEngine
import claripy

"""
    deregister_tm_clones is a 0 sized local function
    register_tm_clones is a 0 sized local function

"""

def identify_functions_from_glibc_entry(b, s:Symbol):
    """
        Only true for Linux x86_64, does not work for OpenBSD binaries
    """
    """
    ['xor ebp, ebp',
     'mov r9, rdx',
     'pop rsi',
     'mov rdx, rsp',
     'and rsp, 0xfffffffffffffff0',
     'push rax',
     'push rsp',
     'lea r8, [rip + 0x39ba]', address of libc_csu_fini
     'lea rcx, [rip + 0x3943]', address of libc_csu_init
     'lea rdi, [rip - 0x1794]', address of main
     'call qword ptr [rip + 0x205fbe]', address of libc_start_main (dynamically linked)
     'hlt']

     lib_csu_init calls '_init' function
    """
    symbols = [ { 'vaddr': s.vaddr, 'name': 'start', 'real_name': '_start' } ]

    see         = SymbolicExecutionEngine(b.config, b)
    see.solver  = claripy.solvers.SolverConcrete()
    lva         = LiveVariableAnalysis(b.config, s)

    func_args, heap_args, tls_args, live_locals, local_stack_bytes, num_locals, resolved = lva.analyse(see)

    for reg, func_name, real_name in [ ('rdi', 'main', 'main'), ('rcx', 'csu_init', '__libc_csu_init'), ('r8', 'csu_fini', '__libc_csu_fini') ]:
        r_reg = dict(filter(lambda x: reg in x[0], resolved.items()))
        assert(len(r_reg) == 1)
        reg_value = list(r_reg.values())[0]
        assert(reg_value)
        symbols.append( { 'name' : func_name, 'vaddr' : reg_value, 'real_name': real_name } )

        if real_name == '__libc_csu_init':
            init = identify_functions_from_glibc_csu_init(b, b.symbol_mapper[reg_value])
            symbols.append(init)

    return symbols

def identify_functions_from_glibc_csu_init(b, s:Symbol):
    """
    │           0x00006950      4157           push r15
    │           0x00006952      4156           push r14
    │           0x00006954      4189ff         mov r15d, edi               ; arg1
    │           0x00006957      4155           push r13
    │           0x00006959      4154           push r12
    │           0x0000695b      4c8d25662420.  lea r12, obj.__frame_dummy_init_array_entry ; loc.__init_array_start
    │                                                                      ; 0x208dc8
    │           0x00006962      55             push rbp
    │           0x00006963      488d2d662420.  lea rbp, obj.__do_global_dtors_aux_fini_array_entry ; loc.__init_array_end
    │                                                                      ; 0x208dd0
    │           0x0000696a      53             push rbx
    │           0x0000696b      4989f6         mov r14, rsi                ; arg2
    │           0x0000696e      4989d5         mov r13, rdx                ; arg3
    │           0x00006971      4c29e5         sub rbp, r12
    │           0x00006974      4883ec08       sub rsp, 8
    │           0x00006978      48c1fd03       sar rbp, 3
    │           0x0000697c      e87fabffff     call sym._init
    │           0x00006981      4885ed         test rbp, rbp
    │       ┌─< 0x00006984      7420           je 0x69a6
    │       │   0x00006986      31db           xor ebx, ebx
    │       │   0x00006988      0f1f84000000.  nop dword [rax + rax]
    │       │   ; CODE XREF from sym.__libc_csu_init @ 0x69a4
    │      ┌──> 0x00006990      4c89ea         mov rdx, r13
    │      ╎│   0x00006993      4c89f6         mov rsi, r14
    │      ╎│   0x00006996      4489ff         mov edi, r15d
    │      ╎│   0x00006999      41ff14dc       call qword [r12 + rbx*8]
    │      ╎│   0x0000699d      4883c301       add rbx, 1
    │      ╎│   0x000069a1      4839dd         cmp rbp, rbx
    │      └──< 0x000069a4      75ea           jne 0x6990
    │       │   ; CODE XREF from sym.__libc_csu_init @ 0x6984
    │       └─> 0x000069a6      4883c408       add rsp, 8
    │           0x000069aa      5b             pop rbx
    │           0x000069ab      5d             pop rbp
    │           0x000069ac      415c           pop r12
    │           0x000069ae      415d           pop r13
    │           0x000069b0      415e           pop r14
    │           0x000069b2      415f           pop r15
    └           0x000069b4      c3             ret
    """
    for ext_vaddr, ext_type in s.bbs[0].exits:
        if ext_type == 'Ijk_Call':
            return { 'name' : 'init', 'real_name' : '_init', 'vaddr': ext_vaddr }

    raise RuntimeError("Error determining _init symbol from static rules!")

"""
 register_tm_clones alwas loads in TMC_END object, refs init0
 entry.init0 can also be calculated

"""
