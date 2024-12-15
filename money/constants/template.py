from cmdapp.render import Template, ResponseFormatter

TEMPLATES = {
    "action": Template(
        "+[{style}]@[ on {action}][ {what}][ within {scope}][ with {argument}][ = {value}][ because {reason}][: |result][{result}]"
    ),
    "argument": Template(
        "[ The argument][ \[{argument}\]][ is {status}][ because {reason}][. {result}][. {recommend}]"
    ),
    "found": Template(
        "[NOT |negative][FOUND][ {count}][/{total}][ {what}][ for {inside}][ with {field}][: {items}][. {result}]"
    ),
    "exception": Template(
        "/*R[ERROR][ \[{type}\]][: |message]*Y['{message}']/*R[ on executing:\n|command]@C[{command}]@R[\n with |argument]@Y[{argument}]"
    ),
}


RESPONSE_FORMATTER = ResponseFormatter(TEMPLATES)
