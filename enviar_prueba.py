import argparse
import sys

from lib.correo import enviar_correo


def main() -> int:
    parser = argparse.ArgumentParser(description="Envía un correo SMTP de prueba.")
    parser.add_argument("destinatario", help="Dirección que recibirá el mensaje de prueba")
    args = parser.parse_args()
    sent = enviar_correo(
        args.destinatario,
        "Prueba de correo - Ferretería Bimetálica",
        "<p>El envío de correo está configurado correctamente.</p>",
        "El envío de correo está configurado correctamente.",
    )
    if not sent:
        print("No se pudo enviar el correo. Revisa MAIL_ENABLED y la configuración SMTP.")
        return 1
    print("Correo de prueba enviado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
