import pygame

class Sprite(pygame.sprite.Sprite):
    def __init__(self, image, pos):
        super().__init__()
        self.image = image
        self.rect = self.image.get_rect(topleft=pos)
        self.mask = pygame.mask.from_surface(self.image)
        self.speed = 24
        self.disabled = False
        
    def update(self, dt: float):
        # Only needed if you want automatic movement or animation
        pass 

    def collidepoint(self, pos):
        if self.disabled is True:
            return False
        
        x = pos[0] - self.rect.x
        y = pos[1] - self.rect.y

        # Avoid index error
        if 0 <= x < self.rect.width and 0 <= y < self.rect.height:
            return self.mask.get_at((x, y))
        return False

    def colliderect(self, *args):
        return self.rect.colliderect(*args)

    def collide(self, *args):
        return self.rect.collide(*args)

    def contains(self, *args):
        return self.rect.contains(*args)

    def clip(self, *args):
        return self.rect.clip(*args)


    @property
    def pos(self):
        return (self.rect.x, self.rect.y)

    @pos.setter
    def pos(self, value):
        self.rect.topleft = value

    @property
    def x(self):
        return self.rect.x

    @x.setter
    def x(self, value):
        self.rect.x = value

    @property
    def y(self):
        return self.rect.y

    @y.setter
    def y(self, value):
        self.rect.y = value
