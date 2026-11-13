-- SQL Server Simulator v0.3 | Designed and developed by Ali Sayyadi
-- Exported: 2026-11-12 02:52 | Target SQL Server: 2022 | Scope: both
-- Educational T-SQL script export, NOT a SQL Server .bak backup.
-- Review and test on a non-production SQL Server instance before deployment.
-- Only supported table columns, primary keys, foreign keys and data are exported.
-- User-created triggers, views, procedures, indexes, collations and permissions are NOT exported.
SET NOCOUNT ON;
GO

IF DB_ID(N'TeachingDB') IS NULL
    EXEC(N'CREATE DATABASE [TeachingDB]');
GO
USE [TeachingDB];
GO

CREATE TABLE [dbo].[Course] (
    [CourseID] INT IDENTITY(1,1) NOT NULL,
    [CourseName] NVARCHAR(MAX) NOT NULL,
    CONSTRAINT [PK_Course] PRIMARY KEY ([CourseID])
);
GO

CREATE TABLE [dbo].[Department] (
    [DepartmentID] INT IDENTITY(1,1) NOT NULL,
    [Title] NVARCHAR(MAX) NOT NULL,
    CONSTRAINT [PK_Department] PRIMARY KEY ([DepartmentID])
);
GO

CREATE TABLE [dbo].[Enrollment] (
    [Student_StudentID] INT NOT NULL,
    [Course_CourseID] INT NOT NULL,
    CONSTRAINT [PK_Enrollment] PRIMARY KEY ([Student_StudentID], [Course_CourseID])
);
GO

CREATE TABLE [dbo].[Profile] (
    [StudentID] INT NOT NULL,
    [Phone] NVARCHAR(MAX) NULL,
    CONSTRAINT [PK_Profile] PRIMARY KEY ([StudentID])
);
GO

CREATE TABLE [dbo].[Student] (
    [StudentID] INT IDENTITY(1,1) NOT NULL,
    [FullName] NVARCHAR(MAX) NOT NULL,
    [DepartmentID] INT NULL,
    CONSTRAINT [PK_Student] PRIMARY KEY ([StudentID])
);
GO

SET IDENTITY_INSERT [dbo].[Course] ON;
INSERT INTO [dbo].[Course] ([CourseID], [CourseName]) VALUES (1, N'Database Lab');
SET IDENTITY_INSERT [dbo].[Course] OFF;
-- Course: 1 row(s) scripted
GO

SET IDENTITY_INSERT [dbo].[Department] ON;
INSERT INTO [dbo].[Department] ([DepartmentID], [Title]) VALUES (1, N'مهندسی کامپیوتر');
SET IDENTITY_INSERT [dbo].[Department] OFF;
-- Department: 1 row(s) scripted
GO

INSERT INTO [dbo].[Enrollment] ([Student_StudentID], [Course_CourseID]) VALUES (1, 1);
-- Enrollment: 1 row(s) scripted
GO

-- Profile: 0 row(s) scripted
GO

SET IDENTITY_INSERT [dbo].[Student] ON;
INSERT INTO [dbo].[Student] ([StudentID], [FullName], [DepartmentID]) VALUES (1, N'Ali Sayyadi', 1);
SET IDENTITY_INSERT [dbo].[Student] OFF;
-- Student: 1 row(s) scripted
GO

ALTER TABLE [dbo].[Enrollment] WITH CHECK ADD CONSTRAINT [FK_Enrollment_Course_1] FOREIGN KEY ([Course_CourseID]) REFERENCES [dbo].[Course] ([CourseID]);
GO
ALTER TABLE [dbo].[Enrollment] WITH CHECK ADD CONSTRAINT [FK_Enrollment_Student_2] FOREIGN KEY ([Student_StudentID]) REFERENCES [dbo].[Student] ([StudentID]);
GO
ALTER TABLE [dbo].[Profile] WITH CHECK ADD CONSTRAINT [FK_Profile_Student_1] FOREIGN KEY ([StudentID]) REFERENCES [dbo].[Student] ([StudentID]);
GO
ALTER TABLE [dbo].[Student] WITH CHECK ADD CONSTRAINT [FK_Student_Department_1] FOREIGN KEY ([DepartmentID]) REFERENCES [dbo].[Department] ([DepartmentID]);
GO
-- End of SQL Server-compatible educational script.
