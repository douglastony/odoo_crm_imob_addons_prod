from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, AccessError


class TestUserRestrictions(TransactionCase):

    def setUp(self):
        super().setUp()
        self.ResUsers = self.env['res.users']
        self.SalesUnit = self.env['crm.sales.unit']

        # Criar unidade raiz
        self.root_unit = self.SalesUnit.create({'name': 'Diretoria A'})
        self.child_unit = self.SalesUnit.create({'name': 'Gerência A1', 'parent_id': self.root_unit.id})

        # Criar diretor
        self.director = self.ResUsers.create({
            'name': 'Diretor',
            'login': 'director@test.com',
            'sales_unit_id': self.root_unit.id,
            'groups_id': [(6, 0, [self.env.ref("crm_sales_unit.group_director").id])]
        })

    def test_director_can_create_in_child_unit(self):
        """Diretor pode criar usuários em subunidades da sua diretoria"""
        with self.env.user(self.director):
            user = self.ResUsers.create({
                'name': 'Teste',
                'login': 'teste@test.com',
                'sales_unit_id': self.child_unit.id
            })
            self.assertEqual(user.sales_unit_id, self.child_unit)

    def test_coordinator_cannot_move_users(self):
        """Coordenador não pode mover usuários entre unidades"""
        coordinator = self.ResUsers.create({
            'name': 'Coord',
            'login': 'coord@test.com',
            'sales_unit_id': self.child_unit.id,
            'groups_id': [(6, 0, [self.env.ref("crm_sales_unit.group_coordinator").id])]
        })

        with self.env.user(coordinator):
            with self.assertRaises(AccessError):
                self.director.write({'sales_unit_id': self.child_unit.id})
