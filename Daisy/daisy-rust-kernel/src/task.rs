#![allow(dead_code)]
use alloc::collections::BTreeMap;
use alloc::string::String;
use alloc::vec::Vec;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TaskState {
    Ready,
    Running,
    Blocked,
    Dead,
}

#[derive(Clone, Debug)]
pub struct Task {
    pub id: u64,
    pub name: String,
    pub state: TaskState,
    pub parent_id: u64,
    pub priority: u8,
    pub caps: Vec<u64>,
}

pub struct TaskManager {
    tasks: BTreeMap<u64, Task>,
    next_id: u64,
}

impl Default for TaskManager {
    fn default() -> Self { Self::new() }
}

impl TaskManager {
    pub fn new() -> Self {
        Self { tasks: BTreeMap::new(), next_id: 0 }
    }

    pub fn create_task(&mut self, name: &str, parent_id: u64, priority: u8) -> u64 {
        let id = self.next_id;
        self.next_id += 1;
        self.tasks.insert(id, Task {
            id,
            name: String::from(name),
            state: TaskState::Ready,
            parent_id,
            priority,
            caps: Vec::new(),
        });
        id
    }

    pub fn destroy_task(&mut self, id: u64) -> bool {
        if let Some(task) = self.tasks.get_mut(&id) {
            task.state = TaskState::Dead;
            true
        } else {
            false
        }
    }

    #[inline]
    pub fn get(&self, id: u64) -> Option<&Task> {
        self.tasks.get(&id)
    }

    #[inline]
    pub fn get_mut(&mut self, id: u64) -> Option<&mut Task> {
        self.tasks.get_mut(&id)
    }

    #[inline]
    pub fn exists(&self, id: u64) -> bool {
        self.tasks.contains_key(&id)
    }

    #[inline]
    pub fn is_alive(&self, id: u64) -> bool {
        self.tasks.get(&id).map_or(false, |t| !matches!(t.state, TaskState::Dead))
    }

    pub fn count_alive(&self) -> usize {
        self.tasks.values().filter(|t| !matches!(t.state, TaskState::Dead)).count()
    }
}
