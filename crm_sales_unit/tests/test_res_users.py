from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, AccessError, ValidationError


class TestResUsers(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Users = self.env['res.users']
        self.SalesUnit = self.env['crm.sales.unit']
        self.admin = self.env.ref("base.user_admin")

        # Criar hierarquia de unidades
        self.directoria = self.SalesUnit.create({
            'name': 'Diretoria A',
            'type': 'diretoria',
            'responsible_id': self.admin.id,
        })
        self.gerencia = self.SalesUnit.create({
            'name': 'Gerência A',
            'type': 'gerencia',
            'parent_id': self.directoria.id,
            'responsible_id': self.admin.id,
        })
        self.coordenacao = self.SalesUnit.create({
            'name': 'Coordenação A',
            'type': 'coordenacao',
            'parent_id': self.gerencia.id,
            'responsible_id': self.admin.id,
        })

        # Criar perfis de teste
        self.socio = self._make_user("Sócio", "socio", "crm_sales_unit.group_president", None)
        self.diretor = self._make_user("Diretor", "diretor", "crm_sales_unit.group_director", self.directoria.id)
        self.gerente = self._make_user("Gerente", "gerente", "crm_sales_unit.group_manager", self.gerencia.id)
        self.coordenador = self._make_user("Coordenador", "coordenador", "crm_sales_unit.group_coordinator", self.coordenacao.id)

    def _make_user(self, name, login, group_xmlid, sales_unit_id):
        """Cria usuários de teste vinculados a unidades e grupos"""
        return self.Users.create({
            'name': name,
            'login': login,
            'sales_unit_id': sales_unit_id,
            'groups_id': [(6, 0, [self.env.ref(group_xmlid).id])],
        })

    # ===========================
    # TESTES DE CRIAÇÃO
    # ===========================

    def test_coordenador_so_cria_na_propria_unidade(self):
        with self.assertRaises(UserError):
            self.Users.with_user(self.coordenador).create({
                'name': 'Invasor',
                'login': 'inv',
                'sales_unit_id': self.gerencia.id,
            })

        novo = self.Users.with_user(self.coordenador).create({
            'name': 'Correto',
            'login': 'cor',
        })
        self.assertEqual(novo.sales_unit_id, self.coordenador.sales_unit_id)

    def test_gerente_cria_dentro_da_arvore(self):
        novo = self.Users.with_user(self.gerente).create({
            'name': 'Coordenação',
            'login': 'coord',
            'sales_unit_id': self.coordenacao.id,
        })
        self.assertEqual(novo.sales_unit_id, self.coordenacao)

        outra_diretoria = self.SalesUnit.create({
            'name': 'Diretoria B',
            'type': 'diretoria',
            'responsible_id': self.admin.id,
        })
        with self.assertRaises(UserError):
            self.Users.with_user(self.gerente).create({
                'name': 'Fora',
                'login': 'fora',
                'sales_unit_id': outra_diretoria.id,
            })

    def test_diretor_cria_em_toda_a_diretoria(self):
        novo = self.Users.with_user(self.diretor).create({
            'name': 'Descendente',
            'login': 'desc',
            'sales_unit_id': self.coordenacao.id,
        })
        self.assertEqual(novo.sales_unit_id, self.coordenacao)

        outra_diretoria = self.SalesUnit.create({
            'name': 'Diretoria X',
            'type': 'diretoria',
            'responsible_id': self.admin.id,
        })
        with self.assertRaises(UserError):
            self.Users.with_user(self.diretor).create({
                'name': 'Invasor',
                'login': 'inv2',
                'sales_unit_id': outra_diretoria.id,
            })

    def test_socio_cria_sem_restricao(self):
        outra_diretoria = self.SalesUnit.create({
            'name': 'Diretoria Livre',
            'type': 'diretoria',
            'responsible_id': self.admin.id,
        })
        novo = self.Users.with_user(self.socio).create({
            'name': 'Livre',
            'login': 'livre',
            'sales_unit_id': outra_diretoria.id,
        })
        self.assertEqual(novo.sales_unit_id, outra_diretoria)

    # ===========================
    # TESTES DE MOVIMENTAÇÃO
    # ===========================

    def test_coordenador_nao_pode_mover(self):
        user = self._make_user("Vendedor", "vend1", "base.group_user", self.coordenacao.id)
        with self.assertRaises(AccessError):
            user.with_user(self.coordenador).write({'sales_unit_id': self.gerencia.id})

    def test_gerente_pode_mover_dentro_da_arvore(self):
        user = self._make_user("Vendedor", "vend2", "base.group_user", self.coordenacao.id)
        user.with_user(self.gerente).write({'sales_unit_id': self.coordenacao.id})
        self.assertEqual(user.sales_unit_id, self.coordenacao)

        outra_diretoria = self.SalesUnit.create({
            'name': 'Diretoria Y',
            'type': 'diretoria',
            'responsible_id': self.admin.id,
        })
        with self.assertRaises(AccessError):
            user.with_user(self.gerente).write({'sales_unit_id': outra_diretoria.id})

    def test_diretor_pode_mover_dentro_da_sua_diretoria(self):
        user = self._make_user("Vendedor", "vend3", "base.group_user", self.coordenacao.id)
        user.with_user(self.diretor).write({'sales_unit_id': self.gerencia.id})
        self.assertEqual(user.sales_unit_id, self.gerencia)

        outra_diretoria = self.SalesUnit.create({
            'name': 'Diretoria Z',
            'type': 'diretoria',
            'responsible_id': self.admin.id,
        })
        with self.assertRaises(AccessError):
            user.with_user(self.diretor).write({'sales_unit_id': outra_diretoria.id})

    def test_socio_pode_mover_sem_restricao(self):
        user = self._make_user("Vendedor", "vend4", "base.group_user", self.coordenacao.id)
        outra_diretoria = self.SalesUnit.create({
            'name': 'Diretoria Livre 2',
            'type': 'diretoria',
            'responsible_id': self.admin.id,
        })
        user.with_user(self.socio).write({'sales_unit_id': outra_diretoria.id})
        self.assertEqual(user.sales_unit_id, outra_diretoria)

    # ===========================
    # TESTES DE UNICIDADE DE CARGO
    # ===========================

    def test_usuario_nao_pode_ter_multiplos_cargos(self):
        with self.assertRaises(ValidationError):
            self.Users.create({
                'name': 'Acumula',
                'login': 'acumula',
                'sales_unit_id': self.directoria.id,
                'groups_id': [(6, 0, [
                    self.env.ref("crm_sales_unit.group_manager").id,
                    self.env.ref("crm_sales_unit.group_director").id,
                ])],
            })
