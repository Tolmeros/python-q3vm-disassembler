#!/usr/bin/env python
import os, sys
from pycparser import parse_file, c_ast

# gcc -nostdinc -m32 -I /usr/share/python-pycparser/fake_libc_include -E q_shared.h  > /share/tmp/q_shared-E-3.h

def usage ():
    sys.stderr.write("%s [--debug, --print-all] <c file> [name]\n" % os.path.basename(sys.argv[0]))
    sys.exit(1)

def output (msg):
    sys.stdout.write(msg)

def error_msg (msg):
    sys.stderr.write("ERROR: %s\n" % msg)

def error_exit (msg):
    error_msg(msg)
    sys.exit(1)

# from CFFI  https://cffi.readthedocs.io/en/latest/  : _parse_constant()

def parse_binaryop (exprnode, partial_length_ok=False):
    # for now, limited to expressions that are an immediate number
    # or positive/negative number
    if isinstance(exprnode, c_ast.Constant):
        s = exprnode.value
        if s.startswith('0'):
            if s.startswith('0x') or s.startswith('0X'):
                return int(s, 16)
            return int(s, 8)
        elif '1' <= s[0] <= '9':
            return int(s, 10)
        elif s[0] == "'" and s[-1] == "'" and (
                len(s) == 3 or (len(s) == 4 and s[1] == "\\")):
            return ord(s[-2])
        else:
            #raise CDefError("invalid constant %r" % (s,))
            error_exit("invalid constant %r" % (s,))
    #
    if (isinstance(exprnode, c_ast.UnaryOp) and
            exprnode.op == '+'):
        return parse_binaryop(exprnode.expr)
    #
    if (isinstance(exprnode, c_ast.UnaryOp) and
            exprnode.op == '-'):
        return -parse_binaryop(exprnode.expr)

    # load previously defined int constant
    ##if (isinstance(exprnode, c_ast.ID) and
    ##        exprnode.name in self._int_constants):
    ##    return self._int_constants[exprnode.name]
    #
    ##if (isinstance(exprnode, pycparser.c_ast.ID) and
    ##            exprnode.name == '__dotdotdotarray__'):
    ##    if partial_length_ok:
    ##        self._partial_length = True
    ##        return '...'
    ##    raise FFIError(":%d: unsupported '[...]' here, cannot derive "
    ##                   "the actual array length in this context"
    ##                   % exprnode.coord.line)

    #
    if (isinstance(exprnode, c_ast.BinaryOp) and
            exprnode.op == '+'):
        return (parse_binaryop(exprnode.left) +
                parse_binaryop(exprnode.right))
    #
    if (isinstance(exprnode, c_ast.BinaryOp) and
            exprnode.op == '-'):
        return (parse_binaryop(exprnode.left) -
                parse_binaryop(exprnode.right))
    #
    ##raise FFIError(":%d: unsupported expression: expected aw "
    ##               "simple numeric constant" % exprnode.coord.line)
    error_exit(":%d: unsupported expression: expected aw simple numeric constant" % exprnode.coord.line)

# structNames: [ name1:str, name2:str, ... ]
# arrayConstants: dotname:str -> [ level1:str, level2:str, ... ]

def print_struct (ast, printAll=False, structNames=[], arrayConstants={}, debugLevel=0):

    for node in ast.ext:
        # typedef struct [name] { ... } tname;
        #if type(node) == c_ast.Typedef  and  node.type == c_ast.TypeDecl  and  type(node.type) == c_ast.Struct:
        if type(node) == c_ast.Typedef  and  type(node.type) == c_ast.TypeDecl  and  type(node.type.type) == c_ast.Struct:
            if not printAll  and  node.name not in structNames:
                continue

            structName = node.type.type.name

            if debugLevel > 0:
                if debugLevel > 1:
                    output("%s : \n" % node.name)
                    output("%s\n\n" % node)
                output("%s (members) : \n" % node.name)
                output("%s\n" % node.type.type.decls)
                output("\n")

            output("%s {\n" % node.name)
            # struct members
            for m in node.type.type:
                #output(" %s : %s " % (m.name, type(m.type)))
                #output("%s" % m.type)
                #output("    %s\n" % m.name)

                mType = type(m.type)

                # straight declaration, ex: int count
                if mType == c_ast.TypeDecl:
                    if type(m.type.type) == c_ast.IdentifierType:
                        output("    %s %s\n" % (m.type.type.names[0], m.name))
                    else:
                        error_exit("not IdentifierType for %s: %s" % (m.name, type(m.type.type)))
                # pointer (straight declaration or function), ex: float *range, int (*func)(int a, int b)
                elif mType == c_ast.PtrDecl:
                    if type(m.type.type) == c_ast.TypeDecl:
                        if type(m.type.type.type) == c_ast.IdentifierType:
                            output("    *%s %s\n" % (m.type.type.type.names[0], m.name))
                        elif type(m.type.type.type) == c_ast.Struct:
                            # check if this is pointer to self
                            if m.type.type.type.name == structName:
                                output("    *%s %s\n" % (node.name, m.name))
                            else:
                                output("    *%s %s\n" % (m.type.type.type.name, m.name))
                        else:
                            error_exit("not IdentifierType for pointer %s: %s" % (m.name, type(m.type.type.type)))
                    elif type(m.type.type) == c_ast.FuncDecl:
                        # just a straight pointer in qvmdis
                        #FIXME what would 'int (*func)(int a, int b)[100]' be considered as?
                        output("    *void %s\n" % m.name)
                    else:
                        error_exit("not TypeDecl for pointer %s: %s" % (m.name, type(m.type.type)))
                # arrays, ex: char word[256]...  or  char *strings[256]...
                elif mType == c_ast.ArrayDecl:
                    arrayLengths = []

                    if type(m.type.dim) == c_ast.Constant:
                        arrayLengths.append(m.type.dim.value)
                    elif type(m.type.dim) == type(None):
                        # ex:  char unk[]
                        error_exit("flexible array member not supported: %s" % m.name)
                    elif type(m.type.dim) == c_ast.BinaryOp:
                        arrayLengths.append(parse_binaryop(m.type.dim))
                    else:
                        error_exit("unknown array dim type for %s: %s" % (m.name, type(m.type.dim)))
                    subType = m.type.type

                    while type(subType) == c_ast.ArrayDecl:
                        if type(subType.dim) == c_ast.Constant:
                            #FIXME check dim.type == 'int' ?, ex: int x[2.2]
                            arrayLengths.append(subType.dim.value)
                        elif type(subType.dim) == type(None):
                            # ex:  char[200[]
                            error_exit("flexible sub array member not supported: %s" % m.name)
                        else:
                            error_exit("unknown sub array dim type for %s: %s" % (m.name, type(subType.dim)))
                        subType = subType.type

                    if type(subType) == c_ast.TypeDecl  or  type(subType) == c_ast.PtrDecl:
                        if type(subType) == c_ast.PtrDecl:
                            isPointer = True
                            subType = subType.type
                        else:
                            isPointer = False

                        if type(subType.type) == c_ast.IdentifierType:
                            arrayTypeName = subType.type.names[0]
                        elif isPointer  and  type(subType) == c_ast.FuncDecl:
                            # ex:  int (*func[36])(int a, int b)
                            error_exit("array of function pointers not supported: %s" % m.name)
                        else:
                            error_exit("unknown array typedecl identifier for %s: %s" % (m.name, type(subType.type)))

                        if isPointer:
                            output("    *%s" % arrayTypeName)
                        else:
                            output("    %s" % arrayTypeName)

                        dotName = node.name + "." + m.name
                        if dotName in arrayConstants:
                            ac = arrayConstants[dotName]
                            for a in ac:
                                output("[%s]" % a)
                        else:
                            for a in arrayLengths:
                                output("[%s]" % a)
                        output(" %s\n" % m.name)
                    else:
                        error_exit("unknown array type for %s: %s" % (m.name, type(m.type.type)))
                else:
                    error_exit("unhandled type for %s: %s\n" % (m.name, mType))
            output("}\n\n")

if __name__ == "__main__":
    debugLevel = 0
    printAll = False

    args = []
    args.append(sys.argv[0])
    checkDashOptions = True
    for a in sys.argv[1:]:
        if checkDashOptions:
            if a == "--":
                # all done, pass the rest as is
                checkDashOptions = False
            elif a[0] != '-':
                args.append(a)
                checkDashOptions = False
            elif a == "--debug":
                debugLevel = 1
            elif a == "--debug-node":
                debugLevel = 2
            elif a == "--print-all":
                printAll = True
            else:
                sys.stderr.write("unknown option: %s\n" % a)
                sys.exit(1)
        else:
            args.append(a)

    # c file required
    if len(args) < 2:
        error_msg("missing c file name")
        usage()

    cFileName = args[1]

    if not printAll  and  len(args) < 3:
        error_msg("missing structure name")
        usage()

    if len(args) > 2:
        structNames = [args[2]]
    else:
        structNames = []

    arrayConstants = {}
    # testing
    #arrayConstants["pc_token_t.string"] = ["MAX_TOKENLENGTH"]

    #ast = parse_file(filename=cFileName)
    #ast = parse_file(filename=cFileName, use_cpp=True, cpp_path='cpp', cpp_args=r'-Iutils/fake_libc_include')
    ast = parse_file(filename=cFileName, use_cpp=True, cpp_path='gcc', cpp_args=['-nostdinc', '-m32', '-I', '/usr/share/python-pycparser/fake_libc_include', '-S', '-E'])
    #ast.show()

    print_struct(ast, structNames=structNames, arrayConstants=arrayConstants, printAll=printAll, debugLevel=debugLevel)