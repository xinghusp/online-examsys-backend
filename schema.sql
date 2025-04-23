-- Database Schema for Online Examination System

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT 'User ID',
  `username` VARCHAR(100) UNIQUE NOT NULL COMMENT 'Username (for login)',
  `password_hash` VARCHAR(255) NOT NULL COMMENT 'Hashed password (use bcrypt)',
  `id_number` VARCHAR(50) UNIQUE NULL COMMENT 'Optional ID number (e.g., student ID, employee ID)',
  `full_name` VARCHAR(100) NULL COMMENT 'Optional full name',
  `status` ENUM('active', 'disabled') NOT NULL DEFAULT 'active' COMMENT 'User status',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation timestamp',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last update timestamp'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Stores user account information';

-- ----------------------------
-- Table structure for groups
-- ----------------------------
DROP TABLE IF EXISTS `groups`;
CREATE TABLE `groups` (
  `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT 'Group ID',
  `name` VARCHAR(100) UNIQUE NOT NULL COMMENT 'Group name (e.g., Class A, Department B)',
  `description` TEXT NULL COMMENT 'Group description',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation timestamp',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last update timestamp'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Stores user groups for organization';

-- ----------------------------
-- Table structure for user_groups (Many-to-Many)
-- ----------------------------
DROP TABLE IF EXISTS `user_groups`;
CREATE TABLE `user_groups` (
  `user_id` INT NOT NULL COMMENT 'Foreign key to users table',
  `group_id` INT NOT NULL COMMENT 'Foreign key to groups table',
  PRIMARY KEY (`user_id`, `group_id`),
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`group_id`) REFERENCES `groups`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Maps users to groups (many-to-many)';

-- ----------------------------
-- Table structure for roles
-- ----------------------------
DROP TABLE IF EXISTS `roles`;
CREATE TABLE `roles` (
  `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT 'Role ID',
  `name` VARCHAR(100) UNIQUE NOT NULL COMMENT 'Role name (e.g., Admin, Examiner, Student)',
  `description` TEXT NULL COMMENT 'Role description',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation timestamp',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last update timestamp'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Stores user roles defining permissions';

-- ----------------------------
-- Table structure for permissions
-- ----------------------------
DROP TABLE IF EXISTS `permissions`;
CREATE TABLE `permissions` (
  `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT 'Permission ID',
  `code` VARCHAR(100) UNIQUE NOT NULL COMMENT 'Permission code (e.g., manage_users, create_exam)',
  `description` TEXT NULL COMMENT 'Permission description'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Defines specific system permissions';

-- ----------------------------
-- Table structure for role_permissions (Many-to-Many)
-- ----------------------------
DROP TABLE IF EXISTS `role_permissions`;
CREATE TABLE `role_permissions` (
  `role_id` INT NOT NULL COMMENT 'Foreign key to roles table',
  `permission_id` INT NOT NULL COMMENT 'Foreign key to permissions table',
  PRIMARY KEY (`role_id`, `permission_id`),
  FOREIGN KEY (`role_id`) REFERENCES `roles`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`permission_id`) REFERENCES `permissions`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Maps permissions to roles (many-to-many)';

-- ----------------------------
-- Table structure for user_roles (Many-to-Many)
-- ----------------------------
DROP TABLE IF EXISTS `user_roles`;
CREATE TABLE `user_roles` (
  `user_id` INT NOT NULL COMMENT 'Foreign key to users table',
  `role_id` INT NOT NULL COMMENT 'Foreign key to roles table',
  PRIMARY KEY (`user_id`, `role_id`),
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`role_id`) REFERENCES `roles`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Assigns roles to users (many-to-many)';

-- ----------------------------
-- Table structure for question_libs (Question Banks)
-- ----------------------------
DROP TABLE IF EXISTS `question_libs`;
CREATE TABLE `question_libs` (
  `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT 'Question Bank ID',
  `name` VARCHAR(255) NOT NULL COMMENT 'Name of the question bank',
  `description` TEXT NULL COMMENT 'Description of the question bank',
  `question_count` INT NOT NULL DEFAULT 0 COMMENT 'Cached total number of questions (managed by triggers or application logic)',
  `creator_id` INT NULL COMMENT 'User ID of the creator',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation timestamp',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last update timestamp',
  FOREIGN KEY (`creator_id`) REFERENCES `users`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Stores question banks (collections of questions)';

-- ----------------------------
-- Table structure for chapters
-- ----------------------------
DROP TABLE IF EXISTS `chapters`;
CREATE TABLE `chapters` (
  `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT 'Chapter ID',
  `question_lib_id` INT NOT NULL COMMENT 'Foreign key to question_libs table',
  `name` VARCHAR(255) NOT NULL COMMENT 'Name of the chapter',
  `description` TEXT NULL COMMENT 'Description of the chapter',
  `order_index` INT DEFAULT 0 COMMENT 'Order within the question bank',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation timestamp',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last update timestamp',
  FOREIGN KEY (`question_lib_id`) REFERENCES `question_libs`(`id`) ON DELETE CASCADE,
  INDEX `idx_chapter_lib` (`question_lib_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Stores chapters within question banks';

-- ----------------------------
-- Table structure for questions
-- ----------------------------
DROP TABLE IF EXISTS `questions`;
CREATE TABLE `questions` (
  `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT 'Question ID',
  `chapter_id` INT NOT NULL COMMENT 'Foreign key to chapters table',
  `question_type` ENUM('single_choice', 'multiple_choice', 'fill_in_blank', 'short_answer') NOT NULL COMMENT 'Type of the question',
  `stem` TEXT NOT NULL COMMENT 'Question text/body (can contain HTML/rich text/formulas)',
  `score` DECIMAL(5, 2) NOT NULL DEFAULT 1.00 COMMENT 'Default score value for this question',
  `options` JSON NULL COMMENT 'Options for choice questions (e.g., [{"id": "A", "text": "..."}, ...])',
  `answer` JSON NULL COMMENT 'Correct answer(s) (e.g., ["A"], ["A", "C"], ["keyword1"], etc.)',
  `grading_strategy` JSON NULL COMMENT 'Specific grading rules (e.g., {"multiple_choice": "partial", "partial_score_percent": 50}, {"fill_in_blank": "contains"})',
  `explanation` TEXT NULL COMMENT 'Optional explanation for the answer',
  `creator_id` INT NULL COMMENT 'User ID of the creator',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation timestamp',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last update timestamp',
  FOREIGN KEY (`chapter_id`) REFERENCES `chapters`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`creator_id`) REFERENCES `users`(`id`) ON DELETE SET NULL,
  INDEX `idx_question_chapter` (`chapter_id`),
  INDEX `idx_question_type` (`question_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Stores individual questions';

-- ----------------------------
-- Table structure for exams
-- ----------------------------
DROP TABLE IF EXISTS `exams`;
CREATE TABLE `exams` (
  `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT 'Exam ID',
  `name` VARCHAR(255) NOT NULL COMMENT 'Name of the exam',
  `start_time` DATETIME NOT NULL COMMENT 'Scheduled start time for the exam',
  `end_time` DATETIME NOT NULL COMMENT 'Scheduled end time for the exam',
  `duration_minutes` INT NOT NULL COMMENT 'Duration of the exam in minutes',
  `show_score_after_exam` BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Whether to show score immediately after submission',
  `show_answers_after_exam` BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Whether to show correct answers after submission/grading',
  `rules` TEXT NULL COMMENT 'Exam rules and instructions (rich text)',
  `paper_generation_mode` ENUM('manual', 'random_unified', 'random_individual') NOT NULL COMMENT 'How the exam paper is generated',
  `status` ENUM('draft', 'published', 'ongoing', 'finished', 'archived') NOT NULL DEFAULT 'draft' COMMENT 'Status of the exam',
  `creator_id` INT NULL COMMENT 'User ID of the creator',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation timestamp',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last update timestamp',
  FOREIGN KEY (`creator_id`) REFERENCES `users`(`id`) ON DELETE SET NULL,
  INDEX `idx_exam_status` (`status`),
  INDEX `idx_exam_time` (`start_time`, `end_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Stores exam definitions and settings';

-- ----------------------------
-- Table structure for exam_questions (Paper composition for manual/random_unified)
-- ----------------------------
DROP TABLE IF EXISTS `exam_questions`;
CREATE TABLE `exam_questions` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `exam_id` INT NOT NULL COMMENT 'Foreign key to exams table',
  `question_id` INT NOT NULL COMMENT 'Foreign key to questions table',
  `score` DECIMAL(5, 2) NOT NULL COMMENT 'Score for this question in this specific exam',
  `order_index` INT NOT NULL COMMENT 'Order of the question in the exam paper',
  FOREIGN KEY (`exam_id`) REFERENCES `exams`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`question_id`) REFERENCES `questions`(`id`) ON DELETE CASCADE,
  UNIQUE KEY `uk_exam_question` (`exam_id`, `question_id`),
  UNIQUE KEY `uk_exam_order` (`exam_id`, `order_index`),
  INDEX `idx_eq_exam` (`exam_id`),
  INDEX `idx_eq_question` (`question_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Defines the structure of exam papers for manual and unified random modes';

-- ----------------------------
-- Table structure for exam_participants
-- ----------------------------
DROP TABLE IF EXISTS `exam_participants`;
CREATE TABLE `exam_participants` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `exam_id` INT NOT NULL COMMENT 'Foreign key to exams table',
  `user_id` INT NULL COMMENT 'Foreign key to users table (if assigning individual user)',
  `group_id` INT NULL COMMENT 'Foreign key to groups table (if assigning group)',
  FOREIGN KEY (`exam_id`) REFERENCES `exams`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`group_id`) REFERENCES `groups`(`id`) ON DELETE CASCADE,
  UNIQUE KEY `uk_exam_user` (`exam_id`, `user_id`),
  UNIQUE KEY `uk_exam_group` (`exam_id`, `group_id`),
  CHECK (`user_id` IS NOT NULL OR `group_id` IS NOT NULL), -- Ensure at least one is assigned
  INDEX `idx_ep_exam` (`exam_id`),
  INDEX `idx_ep_user` (`user_id`),
  INDEX `idx_ep_group` (`group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Maps exams to participants (users or groups)';

-- ----------------------------
-- Table structure for exam_attempts (User's attempt at an exam)
-- ----------------------------
DROP TABLE IF EXISTS `exam_attempts`;
CREATE TABLE `exam_attempts` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Unique ID for each exam attempt',
  `exam_id` INT NOT NULL COMMENT 'Foreign key to exams table',
  `user_id` INT NOT NULL COMMENT 'Foreign key to users table (the examinee)',
  `start_time` DATETIME NULL COMMENT 'Timestamp when the user started the exam',
  `submit_time` DATETIME NULL COMMENT 'Timestamp when the user submitted or was auto-submitted',
  `calculated_end_time` DATETIME NULL COMMENT 'The absolute time the exam must be finished by (start_time + duration)',
  `status` ENUM('pending', 'in_progress', 'submitted', 'grading', 'graded', 'aborted') NOT NULL DEFAULT 'pending' COMMENT 'Status of the attempt',
  `final_score` DECIMAL(7, 2) NULL COMMENT 'Total score achieved after grading',
  `last_heartbeat` TIMESTAMP NULL COMMENT 'Timestamp of the last heartbeat signal received',
  `ip_address` VARCHAR(45) NULL COMMENT 'IP address when starting the exam',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp when the attempt record was created',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last update timestamp',
  FOREIGN KEY (`exam_id`) REFERENCES `exams`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  UNIQUE KEY `uk_attempt_exam_user` (`exam_id`, `user_id`), -- Usually one attempt per user per exam
  INDEX `idx_attempt_exam` (`exam_id`),
  INDEX `idx_attempt_user` (`user_id`),
  INDEX `idx_attempt_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Records each user attempt for an exam';

-- ----------------------------
-- Table structure for exam_attempt_papers (Individual papers for random_individual mode)
-- ----------------------------
DROP TABLE IF EXISTS `exam_attempt_papers`;
CREATE TABLE `exam_attempt_papers` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `attempt_id` BIGINT NOT NULL COMMENT 'Foreign key to exam_attempts table',
  `question_id` INT NOT NULL COMMENT 'Foreign key to questions table',
  `score` DECIMAL(5, 2) NOT NULL COMMENT 'Score assigned to this question for this attempt',
  `order_index` INT NOT NULL COMMENT 'Order of the question in this specific paper',
  FOREIGN KEY (`attempt_id`) REFERENCES `exam_attempts`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`question_id`) REFERENCES `questions`(`id`) ON DELETE CASCADE, -- Consider ON DELETE RESTRICT if questions shouldn't be deleted if part of an attempt
  UNIQUE KEY `uk_attempt_paper_question` (`attempt_id`, `question_id`),
  UNIQUE KEY `uk_attempt_paper_order` (`attempt_id`, `order_index`),
  INDEX `idx_ap_attempt` (`attempt_id`),
  INDEX `idx_ap_question` (`question_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Stores the specific questions for attempts in random_individual mode';

-- ----------------------------
-- Table structure for answers (User's answers to questions in an attempt)
-- ----------------------------
DROP TABLE IF EXISTS `answers`;
CREATE TABLE `answers` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Unique ID for each answer',
  `attempt_id` BIGINT NOT NULL COMMENT 'Foreign key to exam_attempts table',
  `question_id` INT NOT NULL COMMENT 'Foreign key to questions table',
  `user_answer` TEXT NULL COMMENT 'User submitted answer (JSON for choice/fill, text for short answer)',
  `score` DECIMAL(5, 2) NULL COMMENT 'Score awarded for this answer (can be partial)',
  `is_correct` BOOLEAN NULL COMMENT 'Flag indicating if the auto-graded answer is correct',
  `grader_id` INT NULL COMMENT 'User ID of the manual grader (if applicable)',
  `grading_comments` TEXT NULL COMMENT 'Comments from the manual grader',
  `graded_at` TIMESTAMP NULL COMMENT 'Timestamp when manual grading was done',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp when answer was saved/submitted',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last update timestamp',
  FOREIGN KEY (`attempt_id`) REFERENCES `exam_attempts`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`question_id`) REFERENCES `questions`(`id`) ON DELETE CASCADE, -- Consider ON DELETE RESTRICT
  FOREIGN KEY (`grader_id`) REFERENCES `users`(`id`) ON DELETE SET NULL,
  UNIQUE KEY `uk_answer_attempt_question` (`attempt_id`, `question_id`),
  INDEX `idx_answer_attempt` (`attempt_id`),
  INDEX `idx_answer_question` (`question_id`),
  INDEX `idx_answer_grader` (`grader_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Stores the answers given by users during an exam attempt';

-- ----------------------------
-- Table structure for audit_logs
-- ----------------------------
DROP TABLE IF EXISTS `audit_logs`;
CREATE TABLE `audit_logs` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Log entry ID',
  `user_id` INT NULL COMMENT 'User who performed the action (null for system actions)',
  `ip_address` VARCHAR(45) NULL COMMENT 'IP address of the user',
  `action` VARCHAR(255) NOT NULL COMMENT 'Description of the action performed (e.g., login, create_exam)',
  `target_type` VARCHAR(100) NULL COMMENT 'Type of the entity affected (e.g., exam, user, question)',
  `target_id` VARCHAR(100) NULL COMMENT 'ID of the affected entity',
  `details` JSON NULL COMMENT 'Additional details about the action (e.g., old/new values)',
  `timestamp` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp of the action',
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE SET NULL,
  INDEX `idx_log_user` (`user_id`),
  INDEX `idx_log_action` (`action`),
  INDEX `idx_log_target` (`target_type`, `target_id`),
  INDEX `idx_log_timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Records important system and user actions for auditing';

-- ----------------------------
-- Basic Seed Data (Optional)
-- ----------------------------
-- INSERT INTO `roles` (`name`, `description`) VALUES ('System Admin', 'Full system access');
-- INSERT INTO `permissions` (`code`, `description`) VALUES ('manage_users', 'Can create, edit, delete users');
-- INSERT INTO `permissions` (`code`, `description`) VALUES ('manage_roles', 'Can manage roles and permissions');
-- INSERT INTO `permissions` (`code`, `description`) VALUES ('manage_questions', 'Can manage question banks and questions');
-- INSERT INTO `permissions` (`code`, `description`) VALUES ('manage_exams', 'Can create, manage, and publish exams');
-- INSERT INTO `permissions` (`code`, `description`) VALUES ('grade_exams', 'Can manually grade exam answers');
-- INSERT INTO `permissions` (`code`, `description`) VALUES ('view_results', 'Can view exam results and statistics');
-- INSERT INTO `permissions` (`code`, `description`) VALUES ('take_exams', 'Can participate in exams as a student');

-- -- Assign all permissions to System Admin (example)
-- -- INSERT INTO `role_permissions` (`role_id`, `permission_id`) SELECT (SELECT id FROM roles WHERE name='System Admin'), id FROM permissions;

-- -- Create a default admin user (replace with secure password generation)
-- -- INSERT INTO `users` (`username`, `password_hash`, `full_name`, `status`) VALUES ('admin', '$2b$12$....hashed_password_here....', 'Administrator', 'active');
-- -- Assign System Admin role to the admin user
-- -- INSERT INTO `user_roles` (`user_id`, `role_id`) VALUES ((SELECT id FROM users WHERE username='admin'), (SELECT id FROM roles WHERE name='System Admin'));
