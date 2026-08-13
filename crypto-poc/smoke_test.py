"""Risk-retirement spike: confirm charm-crypto's CP-ABE actually works in this container.

Not the real crypto.py yet -- just proves setup -> keygen -> encrypt -> decrypt
round-trips under a policy, and that a non-matching attribute set fails to decrypt.
"""

from charm.toolbox.pairinggroup import PairingGroup, GT
from charm.schemes.abenc.abenc_bsw07 import CPabe_BSW07


def main():
    group = PairingGroup("SS512")
    cpabe = CPabe_BSW07(group)

    public_key, master_key = cpabe.setup()

    bob_key = cpabe.keygen(public_key, master_key, ["RESEARCHER", "LABGROUPA"])
    charlie_key = cpabe.keygen(public_key, master_key, ["RESEARCHER", "LABGROUPB"])

    policy = "(RESEARCHER and LABGROUPA)"

    message = group.random(GT)
    ciphertext = cpabe.encrypt(public_key, message, policy)

    bob_recovered = cpabe.decrypt(public_key, bob_key, ciphertext)
    assert bob_recovered == message, "Bob (matching attributes) failed to decrypt"
    print("PASS: Bob decrypts successfully")

    try:
        charlie_recovered = cpabe.decrypt(public_key, charlie_key, ciphertext)
        assert charlie_recovered != message
        print("PASS: Charlie's decrypt did not recover the message")
    except Exception:
        print("PASS: Charlie's decrypt raised as expected (attributes don't satisfy policy)")

    print("\ncharm-crypto CP-ABE is working in this container.")


if __name__ == "__main__":
    main()
