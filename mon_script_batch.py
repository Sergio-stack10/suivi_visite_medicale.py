import os
print("Le robot GitHub s'est bien réveillé !")

# Il va lire le mot de passe dans le coffre-fort (Secrets)
mongo_uri = os.environ.get("MONGO_URI")

if mongo_uri:
    print("J'ai bien trouvé l'adresse de la base de données !")
else:
    print("Je n'ai pas trouvé l'adresse...")
