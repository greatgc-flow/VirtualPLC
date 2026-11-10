"""Step 1 - the smallest possible round trip: VirtualPLC + pymcprotocol.

    python 01_hello.py

What happens:
  * Server(port=0) starts a virtual PLC inside this process on a free port.
  * A pymcprotocol client connects like it would to a real Q-series PLC.
  * We write words and bits, read them back, and ask for the CPU model.
"""

from pymcprotocol import Type3E
from virtual_plc import Server


def main():
    # The "with" block starts the simulator and always stops it again.
    # text_pad=0x20 pads the CPU-name text with spaces instead of NUL bytes.
    with Server(port=0, text_pad=0x20) as plc:
        host, port = plc.address  # the free port the OS picked
        print("virtual PLC listening on %s:%d" % (host, port))

        client = Type3E(plctype="Q")  # same call you would use for a real Q PLC
        client.connect(host, port)
        try:
            client.batchwrite_wordunits("D100", [123, -45])  # D100 and D101
            print("D100..D101 =", client.batchread_wordunits("D100", 2))

            client.batchwrite_bitunits("M0", [1, 0, 1])  # M0, M1, M2
            print("M0..M2     =", client.batchread_bitunits("M0", 3))

            cpu_name, model_code = client.read_cputype()  # both returned as text
            print("CPU type   = %r (model code %s)" % (cpu_name.strip(), model_code))
        finally:
            client.close()


if __name__ == "__main__":
    main()
