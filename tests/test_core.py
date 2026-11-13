import sys
import tempfile
from pathlib import Path
import unittest
import sqlite3

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from core import LabDatabase, LabError, Column


class LabTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.db = LabDatabase(Path(self.dir.name) / 'practice.db')

    def tearDown(self):
        self.db.close()
        self.dir.cleanup()

    def test_one_to_one_shared_primary_key_enforced(self):
        self.db.create_table('Person', [Column('id', 'INTEGER', True, True, True)])
        self.db.create_table('Passport', [Column('id', 'INTEGER', True, True), Column('code', 'TEXT')])
        self.db.one_to_one('Person', 'Passport')
        self.assertEqual(self.db.links()[0]['kind'], '1:1')
        with self.assertRaises(LabError):
            self.db.execute('INSERT INTO Passport(id, code) VALUES(99, \'invalid\');')
        self.db.execute('INSERT INTO Person(id) VALUES(1);')
        self.db.execute('INSERT INTO Passport(id, code) VALUES(1, \'valid\');')
        with self.assertRaises(LabError):
            self.db.execute('INSERT INTO Passport(id, code) VALUES(1, \'duplicate\');')

    def test_one_to_many_actual_fk(self):
        self.db.create_table('Department', [Column('id', 'INTEGER', True, True, True)])
        self.db.create_table('Staff', [Column('id', 'INTEGER', True, True, True)])
        self.db.one_to_many('Department', 'Staff', 'department_id')
        cols = {c['name'] for c in self.db.columns('Staff')}
        self.assertIn('department_id', cols)
        self.assertEqual(len(self.db.foreign_keys('Staff')), 1)
        with self.assertRaises(LabError):
            self.db.execute('INSERT INTO Staff(department_id) VALUES(999);')
        with self.assertRaises(LabError):
            self.db.execute('INSERT INTO Staff DEFAULT VALUES;')
        self.db.execute('INSERT INTO Department(id) VALUES(1);')
        self.db.execute('INSERT INTO Staff(department_id) VALUES(1);')

    def test_many_to_many_composite_pk(self):
        self.db.create_table('Student', [Column('id', 'INTEGER', True, True, True)])
        self.db.create_table('Course', [Column('id', 'INTEGER', True, True, True)])
        self.db.many_to_many('Student', 'Course', 'Enroll', 'composite')
        cols = self.db.columns('Enroll')
        self.assertEqual(sum(bool(c['pk']) for c in cols), 2)
        self.assertEqual(len(self.db.foreign_keys('Enroll')), 2)
        self.db.execute('INSERT INTO Student(id) VALUES(1);')
        self.db.execute('INSERT INTO Course(id) VALUES(2);')
        self.db.execute('INSERT INTO Enroll(Student_id, Course_id) VALUES(1,2);')
        with self.assertRaises(LabError):
            self.db.execute('INSERT INTO Enroll(Student_id, Course_id) VALUES(1,2);')

    def test_many_to_many_surrogate_with_unique_pair(self):
        self.db.create_table('Student', [Column('id', 'INTEGER', True, True, True)])
        self.db.create_table('Course', [Column('id', 'INTEGER', True, True, True)])
        self.db.many_to_many('Student', 'Course', 'Enroll', 'surrogate')
        cols = self.db.columns('Enroll')
        self.assertEqual([c['name'] for c in cols if c['pk']], ['JunctionID'])
        self.db.execute('INSERT INTO Student(id) VALUES(1);')
        self.db.execute('INSERT INTO Course(id) VALUES(2);')
        self.db.execute('INSERT INTO Enroll(Student_id, Course_id) VALUES(1,2);')
        with self.assertRaises(LabError):
            self.db.execute('INSERT INTO Enroll(Student_id, Course_id) VALUES(1,2);')

    def test_existing_column_rebuilt_as_fk(self):
        self.db.create_table('Dept', [Column('id', 'INTEGER', True, True, True)])
        self.db.create_table('Employee', [Column('id', 'INTEGER', True, True, True), Column('dept_id', 'INTEGER')])
        self.db.one_to_many('Dept', 'Employee', 'dept_id', required=False)
        self.assertEqual(self.db.foreign_keys('Employee')[0]['from'], 'dept_id')

    def test_demo_and_multi_statement(self):
        self.db.demo()
        self.assertEqual(len(self.db.tables()), 5)
        self.assertEqual(len(self.db.links()), 6)  # 5 physical FKs + conceptual N:M annotation
        names, rows, _ = self.db.execute('INSERT INTO Department(Title) VALUES(\'علوم\');\nSELECT Title FROM Department;')
        self.assertEqual(rows, [('علوم',)])

    def test_prevent_rebuilding_populated_table(self):
        self.db.create_table('P', [Column('id', 'INTEGER', True, True, True)])
        self.db.create_table('C', [Column('id', 'INTEGER', True, True, True)])
        self.db.execute('INSERT INTO C(id) VALUES(10);')
        with self.assertRaises(LabError):
            self.db.one_to_many('P','C','p_id')
        self.assertEqual(self.db.foreign_keys('C'), [])


if __name__ == '__main__':
    unittest.main()
