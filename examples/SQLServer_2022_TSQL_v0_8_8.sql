-- SQL Server Simulator v0.8.8 | Designed and developed by Ali Sayyadi
-- Generated: 2026-11-16 00:33 | Target SQL Server: 2022 | Mode: both
-- Executable T-SQL for the supported table/column/constraint subset.
-- This is a SQL SCRIPT, not a native .bak backup and not a bit-for-bit SSMS export.
-- Review and test against the chosen SQL Server version before deployment.
-- Database users, permissions, views, stored procedures and functions are not included.
SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO
SET ANSI_PADDING ON;
GO
SET NOCOUNT ON;
GO

IF DB_ID(N'SQLSimStudentDemo') IS NULL
    EXEC(N'CREATE DATABASE [SQLSimStudentDemo]');
GO
USE [SQLSimStudentDemo];
GO

-- Table: Course
CREATE TABLE [dbo].[Course] (
    [CourseID] INT IDENTITY(1,1) NOT NULL,
    [Title] NVARCHAR(80) NOT NULL,
    CONSTRAINT [PK_Course] PRIMARY KEY ([CourseID])
);
GO

-- Table: Department
CREATE TABLE [dbo].[Department] (
    [DepartmentID] INT IDENTITY(100,5) NOT NULL,
    [Name] NVARCHAR(60) NOT NULL,
    CONSTRAINT [PK_Department] PRIMARY KEY ([DepartmentID])
);
GO

-- Table: Enrollment
CREATE TABLE [dbo].[Enrollment] (
    [JunctionID] INT IDENTITY(1,1) NOT NULL,
    [Student_StudentID] INT NOT NULL,
    [Course_CourseID] INT NOT NULL,
    CONSTRAINT [PK_Enrollment] PRIMARY KEY ([JunctionID]),
    CONSTRAINT [UQ_Enrollment_1] UNIQUE ([Student_StudentID], [Course_CourseID])
);
GO

-- Table: Student
CREATE TABLE [dbo].[Student] (
    [StudentID] INT IDENTITY(1,1) NOT NULL,
    [FullName] NVARCHAR(80) NOT NULL,
    [DepartmentID] INT NULL,
    CONSTRAINT [PK_Student] PRIMARY KEY ([StudentID])
);
GO

SET IDENTITY_INSERT [dbo].[Course] ON;
INSERT INTO [dbo].[Course] ([CourseID], [Title]) VALUES (1, N'پایگاه داده');
SET IDENTITY_INSERT [dbo].[Course] OFF;
-- Course: 1 row(s) scripted
GO

SET IDENTITY_INSERT [dbo].[Department] ON;
INSERT INTO [dbo].[Department] ([DepartmentID], [Name]) VALUES (100, N'فنی و مهندسی');
SET IDENTITY_INSERT [dbo].[Department] OFF;
-- Department: 1 row(s) scripted
GO

SET IDENTITY_INSERT [dbo].[Enrollment] ON;
INSERT INTO [dbo].[Enrollment] ([JunctionID], [Student_StudentID], [Course_CourseID]) VALUES (1, 1, 1);
SET IDENTITY_INSERT [dbo].[Enrollment] OFF;
-- Enrollment: 1 row(s) scripted
GO

SET IDENTITY_INSERT [dbo].[Student] ON;
INSERT INTO [dbo].[Student] ([StudentID], [FullName], [DepartmentID]) VALUES (1, N'علی', 100);
SET IDENTITY_INSERT [dbo].[Student] OFF;
-- Student: 1 row(s) scripted
GO

ALTER TABLE [dbo].[Enrollment] WITH CHECK ADD CONSTRAINT [FK_Enrollment_Course_1] FOREIGN KEY ([Course_CourseID]) REFERENCES [dbo].[Course] ([CourseID]);
GO
ALTER TABLE [dbo].[Enrollment] CHECK CONSTRAINT [FK_Enrollment_Course_1];
GO

ALTER TABLE [dbo].[Enrollment] WITH CHECK ADD CONSTRAINT [FK_Enrollment_Student_2] FOREIGN KEY ([Student_StudentID]) REFERENCES [dbo].[Student] ([StudentID]);
GO
ALTER TABLE [dbo].[Enrollment] CHECK CONSTRAINT [FK_Enrollment_Student_2];
GO

ALTER TABLE [dbo].[Student] WITH CHECK ADD CONSTRAINT [FK_Student_Department_1] FOREIGN KEY ([DepartmentID]) REFERENCES [dbo].[Department] ([DepartmentID]);
GO
ALTER TABLE [dbo].[Student] CHECK CONSTRAINT [FK_Student_Department_1];
GO

-- End of generated T-SQL script.
