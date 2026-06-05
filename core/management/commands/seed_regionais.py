from django.core.management.base import BaseCommand
from core.models import Regiao, Territorio, Cidade


DATA = {
    "Central": {
        "CAMPINAS": [
            "Amparo",
            "Campinas",
            "Elias Fausto",
            "Holambra",
            "Hortolândia",
            "Jaguariúna",
            "Lindóia",
            "Monte Alegre do Sul",
            "Monte Mor",
            "Pedreira",
            "Santo Antônio de Posse",
            "Serra Negra"
        ],
        "SOROCABA": [
            "Alumínio",
            "Angatuba",
            "Araçoiaba da Serra",
            "Bofete",
            "Boituva",
            "Campina do Monte Alegre",
            "Capela do Alto",
            "Capivari",
            "Cerquilho",
            "Cesário Lange",
            "Conchas",
            "Iperó",
            "Itapetininga",
            "Itu",
            "Jumirim",
            "Laranjal Paulista",
            "Pereiras",
            "Pilar do Sul",
            "Porangaba",
            "Quadra",
            "Rafard",
            "Rio das Pedras",
            "Saltinho",
            "Salto",
            "Salto de Pirapora",
            "Sarapuí",
            "Sorocaba",
            "Tatuí",
            "Tietê",
            "Votorantim"
        ],
        "SUMARÉ": [
            "Aguaí",
            "Americana",
            "Araras",
            "Artur Nogueira",
            "Casa Branca",
            "Conchal",
            "Cordeirópolis",
            "Cosmópolis",
            "Engenheiro Coelho",
            "Estiva Gerbi",
            "Iracemápolis",
            "Leme",
            "Limeira",
            "Mogi Guaçu",
            "Mogi Mirim",
            "Nova Odessa",
            "Paulínia",
            "Piracicaba",
            "Pirassununga",
            "Porto Ferreira",
            "Rio Claro",
            "Santa Bárbara d'Oeste",
            "Santa Cruz das Palmeiras",
            "Santa Gertrudes",
            "Santa Rita do Passa Quatro",
            "Santa Rosa de Viterbo",
            "Sumaré",
            "Tambaú"
        ]
    },
    "Centro Oeste": {
        "ARARAQUARA": [
            "Américo Brasiliense",
            "Araraquara",
            "Boa Esperança do Sul",
            "Borborema",
            "Cravinhos",
            "Descalvado",
            "Dobrada",
            "Gavião Peixoto",
            "Guariba",
            "Guatapará",
            "Ibaté",
            "Ibitinga",
            "Itaju",
            "Itápolis",
            "Matão",
            "Motuca",
            "Nova Europa",
            "Ribeirão Bonito",
            "Ribeirão Preto",
            "Rincão",
            "Santa Ernestina",
            "Santa Lúcia",
            "Serra Azul",
            "São Carlos",
            "Tabatinga",
            "Trabiju"
        ],
        "BARRETOS": [
            "Bady Bassitt",
            "Barretos",
            "Bebedouro",
            "Cedral",
            "Colina",
            "Cristais Paulista",
            "Cândido Rodrigues",
            "Fernando Prestes",
            "Franca",
            "Guapiaçu",
            "Guaíra",
            "Itajobi",
            "Itirapuã",
            "Jaborandi",
            "Jaboticabal",
            "Mirassol",
            "Monte Alto",
            "Olímpia",
            "Patrocínio Paulista",
            "Pindorama",
            "Pitangueiras",
            "Ribeirão Corrente",
            "Santa Adélia",
            "São José do Rio Preto",
            "Taquaritinga",
            "Uchoa"
        ],
        "LENÇÓIS PAULISTA": [
            "Agudos",
            "Arandu",
            "Areiópolis",
            "Avaré",
            "Avaí",
            "Barra Bonita",
            "Bauru",
            "Bocaina",
            "Borebi",
            "Botucatu",
            "Cafelândia",
            "Cerqueira César",
            "Curupá",
            "Dois Córregos",
            "Dourado",
            "Guarantã",
            "Iaras",
            "Igaraçu do Tietê",
            "Itapuí",
            "Itatinga",
            "Itaí",
            "Jaú",
            "Lençóis Paulista",
            "Lins",
            "Macatuba",
            "Manduri",
            "Mineiros do Tietê",
            "Paranapanema",
            "Pardinho",
            "Pederneiras",
            "Pirajuí",
            "Piratininga",
            "Pratânia",
            "Presidente Alves",
            "São Manuel",
            "Vitoriana",
            "Águas de Santa Bárbara",
            "Óleo"
        ]
    },
    "Sudeste": {
        "JUNDIAÍ": [
            "Araçariguama",
            "Atibaia",
            "Bom Jesus dos Perdões",
            "Bragança Paulista",
            "Cabreúva",
            "Caieiras",
            "Campo Limpo Paulista",
            "Franco da Rocha",
            "Indaiatuba",
            "Itupeva",
            "Jarinú",
            "Jundiaí",
            "Louveira",
            "Mairiporã",
            "Nazaré Paulista",
            "Piracaia",
            "Valinhos",
            "Vinhedo",
            "Várzea Paulista"
        ],
        "PRAIA GRANDE": [
            "Cubatão",
            "Guarujá",
            "Itanhaém",
            "Mongaguá",
            "Peruíbe",
            "Praia Grande",
            "Santos",
            "São Bernardo do Campo",
            "São Vicente"
        ],
        "SÃO JOSE DOS CAMPOS": [
            "Biritiba Mirim",
            "Caçapava",
            "Guararema",
            "Igaratá",
            "Jacareí",
            "Mogi das Cruzes",
            "Salesópolis",
            "Santa Branca",
            "São José dos Campos",
            "São Paulo",
            "Taubaté",
            "Tremembé"
        ]
    }
}


class Command(BaseCommand):
    help = 'Seeds regionais, territorios e cidades from Excel data'

    def handle(self, *args, **kwargs):
        created_r = created_t = created_c = 0
        for i, (nome_reg, territorios) in enumerate(DATA.items()):
            regiao, new = Regiao.objects.get_or_create(nome=nome_reg, defaults={'order': i})
            if new: created_r += 1
            for j, (nome_terr, cidades) in enumerate(territorios.items()):
                terr, new = Territorio.objects.get_or_create(regiao=regiao, nome=nome_terr, defaults={'order': j})
                if new: created_t += 1
                for k, nome_cid in enumerate(cidades):
                    cid, new = Cidade.objects.get_or_create(territorio=terr, nome=nome_cid)
                    if new: created_c += 1
        self.stdout.write(self.style.SUCCESS(
            f'Criados: {created_r} regionais, {created_t} territórios, {created_c} cidades.'
        ))